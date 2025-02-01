import argparse
import datetime
import hashlib
import json
import logging
import os.path
import re
import shutil
import sys
from enum import Enum
from pathlib import Path
from typing import ClassVar, Self, Callable, Any
from urllib.parse import urlparse

import yaml
from pydantic import BaseModel, Field, validator
from pydantic.networks import HttpUrl
from requests import Request, Session, PreparedRequest


class AppError(Exception):
    pass


def get_hash_file_digest(hash_file: Path) -> str:
    logging.debug(f'Loading digest from {hash_file}')
    try:
        with open(hash_file, 'r') as f:
            return f.read().split()[0].lower()
    except OSError as e:
        raise AppError(f'Failed to read hash file {hash_file}: {e}')


def get_file_digest(target_file: Path, algorithm: str) -> str:
    logging.debug(f'Computing digest for {target_file} using {algorithm=}')
    try:
        with open(target_file, 'rb') as f:
            # noinspection PyTypeChecker
            return hashlib.file_digest(f, algorithm).hexdigest().lower()  # type hint issue for f
    except OSError as e:
        raise AppError(f'Failed to compute hash for {target_file}: {e}')


def is_digest_valid(target_file: Path, hash_file: Path) -> bool:
    logging.debug(f'Checking {target_file} against {hash_file}')
    fingerprint = get_hash_file_digest(hash_file)
    extension = hash_file.suffix.lower()
    if extension.startswith('.'):
        extension = extension[1:]
    computed = get_file_digest(target_file, extension)
    return computed == fingerprint


class ProductConfig(BaseModel):
    version: str | None
    os: list[str]


class Config(BaseModel):
    DEFAULT_FILE_NAME: ClassVar[str] = 'config.yaml'

    products: dict[str, ProductConfig]
    plugins: list[int]

    @classmethod
    def load(cls, config_file: str = DEFAULT_FILE_NAME) -> Self:
        try:
            with open(config_file, 'rb') as f:
                config = yaml.safe_load(f)
                return Config(**config)
        except OSError as e:
            raise AppError(f'Failed to load {config_file}: {e}')


class JBProductReleaseDownloadInfo(BaseModel):
    link: HttpUrl
    size: int
    checksum_link: HttpUrl = Field(alias='checksumLink')


class JBProductReleaseType(Enum):
    release = 'release'


class JBProductReleaseDownload(BaseModel):
    # some release are missing platforms
    linux: JBProductReleaseDownloadInfo = None
    windows: JBProductReleaseDownloadInfo = None


class JBProductRelease(BaseModel):
    date: datetime.date
    type: JBProductReleaseType
    version: str
    build: str
    downloads: JBProductReleaseDownload


class JBProduct(BaseModel):
    code: str
    name: str
    releases: list[JBProductRelease]

    def get_release(self, version: str) -> JBProductRelease | None:
        return next((release for release in self.releases if release.version == version), None)

    def get_latest_release(self) -> JBProductRelease | None:
        try:
            return self.releases[0]
        except IndexError:
            return None


class JBPlugin(BaseModel):
    id: int
    name: str
    family: str


class JBPluginUpdateBuildValidator:
    # Valid : "", "123", "123.*", "123.456", "123.456.*", "123.456.789"
    RE = re.compile(r'^(|\d+|\d+\.(\d+|\*)|\d+\.\d+\.(\d+|\*))$')

    @classmethod
    def is_valid(cls, value: str) -> str:
        if cls.RE.fullmatch(value) is None:
            raise ValueError(f'Build string `{value}` does not match {cls.RE.pattern} but does not : ')
        return value


class JBPluginUpdate(BaseModel):
    id: int
    version: str
    timestamp_ms: int = Field(alias='cdate')
    since: str = None
    until: str = None

    _since_validator = validator('since', allow_reuse=True)(JBPluginUpdateBuildValidator.is_valid)
    _until_validator = validator('until', allow_reuse=True)(JBPluginUpdateBuildValidator.is_valid)


class UrlTracker(BaseModel):
    DEFAULT_URL_FILE: ClassVar[str] = 'url.json'

    request_hostname: set[str] = Field(default_factory=set)
    response_hostname: set[str] = Field(default_factory=set)
    request_url: set[str] = Field(default_factory=set)
    response_url: set[str] = Field(default_factory=set)

    def track_request_hostname(self, url):
        hostname = urlparse(url).hostname
        if hostname not in self.request_hostname:
            logging.debug(f'Tracking request hostname : {hostname}')
            self.request_hostname.add(hostname)

    def track_response_hostname(self, url):
        hostname = urlparse(url).hostname
        # only add if not already known in request
        if hostname not in self.request_hostname:
            logging.debug(f'Tracking response hostname : {hostname}')
            self.response_hostname.add(hostname)

    def track_request_url(self, url) -> None:
        self.track_request_hostname(url)
        if url not in self.request_url:
            logging.debug(f'Tracking request URL : {url}')
            self.request_url.add(url)

    def track_response_url(self, url) -> None:
        self.track_response_hostname(url)
        # only add if not already known in request
        if url not in self.request_url:
            logging.debug(f'Tracking response URL : {url}')
            self.response_url.add(url)

    # noinspection PyTypeChecker
    def sort_tracked_items(self):
        self.request_hostname = sorted(self.request_hostname)
        self.response_hostname = sorted(self.response_hostname)
        self.request_url = sorted(self.request_url)
        self.response_url = sorted(self.response_url)

    def write_tracked_url(self, directory: Path) -> Path:
        target = directory / self.DEFAULT_URL_FILE
        logging.info(f'Writing tracked url to {target}')
        self.sort_tracked_items()
        try:
            with open(target, 'wt') as f:
                f.write(self.json(indent=4))
        except OSError as e:
            raise AppError(f'Failed to write tracked url {target}: {e}')
        return target


class Cache:

    def get(self, key: str) -> Any:
        raise NotImplementedError()

    def put(self, key: str, value: Any) -> None:
        raise NotImplementedError()


class JetBrainsApi:
    DATA_URL = 'https://data.services.jetbrains.com'
    PLUGIN_URL = 'https://plugins.jetbrains.com'

    def __init__(self, *, tracker: UrlTracker, cache: Cache) -> None:
        self.session = Session()
        self.cache = cache
        self.url_tracker = tracker

    def do_cached_query(self, request: PreparedRequest) -> dict:
        self.url_tracker.track_request_url(request.url)
        try:
            data = self.cache.get(request.url)
        except KeyError:
            response = self.session.send(request)
            self.url_tracker.track_response_url(response.request.url)
            data = response.json()
            self.cache.put(request.url, data)
        return data

    def get_product(self, product_id: str) -> JBProduct:
        params = {"code": product_id, "release.type": JBProductReleaseType.release.value}
        request = Request('GET', f'{self.DATA_URL}/products', params=params).prepare()
        data = self.do_cached_query(request)
        if not isinstance(data, list) or len(data) != 1:
            raise AppError(f'Product information for {product_id} is not in a recognized format')
        return JBProduct(**data[0])

    def get_plugin(self, plugin_id: int) -> JBPlugin:
        logging.debug(f'Getting information for plugin {plugin_id}')
        req = Request('GET', f'{self.PLUGIN_URL}/api/plugins/{plugin_id}').prepare()
        data = self.do_cached_query(req)
        if not isinstance(data, dict):
            raise AppError(f'Plugin information for {plugin_id} is not in a recognized format')
        return JBPlugin(**data)

    def get_plugin_updates(self, plugin_id: int, page: int, page_size: int) -> list[JBPluginUpdate]:
        logging.debug(f'Getting updates for plugin {plugin_id} {page=}({page_size=})')
        params = {'page': page, 'size': page_size}
        req = Request('GET', f'{self.PLUGIN_URL}/api/plugins/{plugin_id}/updates', params=params).prepare()
        data = self.do_cached_query(req)
        if not isinstance(data, list):
            raise AppError(f'Plugin updates for {plugin_id} is not in a recognized format')
        return [JBPluginUpdate(**item) for item in data]

    def get_plugin_updates_all(self, plugin_id: int, page_size: int = 100) -> list[JBPluginUpdate]:
        logging.debug(f'Getting all updates for plugin {plugin_id} ({page_size=})')
        # key=lambda x: x.timestamp_ms, reverse=True
        page = 0
        updates = []
        while True:
            items = self.get_plugin_updates(plugin_id, page, page_size)
            logging.debug(f'Updates received: {len(items)}')
            updates.extend(items)
            if len(items) < page_size:
                break
            page += 1
        logging.info(f'Found {len(updates)} releases for plugin id {plugin_id}')
        return updates

    def download_file(self, url: str, directory: Path, *, params: dict = None) -> Path:
        if params is None:
            params = {}
        logging.debug(f'Downloading {url} to {directory}')
        directory.mkdir(parents=True, exist_ok=True)
        target = None
        try:
            request = Request('GET', url, params=params).prepare()
            self.url_tracker.track_request_url(request.url)
            response = self.session.send(request, stream=True)
            self.url_tracker.track_response_url(response.request.url)
            file = os.path.basename(urlparse(response.request.url).path)
            target = directory / file
            if target.exists():
                logging.debug(f'File {file} already exists: skipping download')
                return target
            logging.info(f'Downloading {file}...')
            with open(target, 'wb') as f:
                # noinspection PyTypeChecker
                shutil.copyfileobj(response.raw, f)  # type hint issue for f
        except Exception as e:
            if target is not None:
                target.unlink(missing_ok=True)
            raise AppError(f'Failed to download {url}, eventual file {target} was purged : {e}')
        return target

    def download_plugin(self, plugin_update_id: int, directory: Path) -> Path:
        params = {'rel': True, 'updateId': plugin_update_id}
        return self.download_file(f'{self.PLUGIN_URL}/plugin/download', directory, params=params)

    @staticmethod
    def get_build_tuple(build: str) -> tuple | None:
        return tuple(int(x) for x in build.split('.') if x.strip() not in ('*', ''))

    @staticmethod
    def is_build_between(since: tuple, target: tuple, until: tuple) -> bool:
        low = since <= target
        high = True
        for target_v, until_v in zip(target, until):
            if target_v < until_v:
                high = True
                break
            if target_v > until_v:
                high = False
                break
        logging.debug(f'Testing for {since} <= {target} <= {until} : {low=} {high=}')
        return low and high


class NoCache(Cache):

    def __init__(self) -> None:
        pass

    def get(self, key: str) -> Any:
        raise KeyError(key)

    def put(self, key: str, value: Any) -> None:
        pass


class DiskCache(BaseModel, Cache):
    destination: Path = Path('cache')
    algorithm: str = 'sha256'

    def __init__(self, **kw):
        super().__init__(**kw)
        try:
            self.destination.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise AppError(f'Failed to ensure cache directory exists: {e}')

    def file_key(self, key: str) -> str:
        h = hashlib.new(self.algorithm)
        h.update(key.encode())
        return h.hexdigest()

    def file_path(self, key: str) -> Path:
        self.destination.mkdir(parents=True, exist_ok=True)
        return self.destination / self.file_key(key)

    def get(self, key: str) -> Any:
        file = self.file_path(key)
        try:
            with open(file, 'rb') as f:
                logging.debug(f'Cache hit for {key} at {file}')
                return json.load(f)
        except FileNotFoundError:
            logging.debug(f'Cache miss for {key} at {file}')
            raise KeyError(key)

    def put(self, key: str, value: Any) -> None:
        file = self.file_path(key)
        try:
            with open(file, 'wt') as f:
                f.write(json.dumps(value))
        except OSError as e:
            raise AppError(f'Could not write disk cache for key {key}: {e}')
        logging.debug(f'Caching flush for {key} at {file}')


class UnknownFilesTracker(BaseModel):
    log_file: str = 'unknown.txt'

    @staticmethod
    def get_unknown_files(destination: Path, known_files: set[Path]) -> list[Path]:
        # sort so that files are first and folders are depth-first
        unknown_files = ((not entry.is_dir(), entry) for entry in destination.rglob('*') if entry not in known_files)
        return [entry[1] for entry in sorted(unknown_files, reverse=True)]

    def write_unknown_files(self, unknown_files: list[Path]) -> None:
        try:
            with open(self.log_file, "wt") as f:
                for entry in unknown_files:
                    f.write(f'{entry}\n')
        except OSError as e:
            raise AppError(f'Could not write list of unknown files : {e}')

    @staticmethod
    def clean_unknown_file(entry):
        logging.info(f'Removing {entry}')
        if entry.is_dir():
            entry.rmdir()
        else:
            entry.unlink(missing_ok=True)

    @classmethod
    def clean_unknown_files(cls, unknown_files: list[Path]) -> None:
        for entry in unknown_files:
            try:
                cls.clean_unknown_file(entry)
            except OSError as e:
                logging.warning(f'Could not remove unknown file {entry} : {e}')


class Hasher:

    @staticmethod
    def get_hash_function(identifier: str) -> Callable:
        match identifier:
            case 'sha256':
                return hashlib.sha256
        raise AppError(f'Unhandled hash identifier {identifier}')


class ProductReleaseOs(BaseModel):
    archive: str
    hash: str


class ProductInfo(BaseModel):
    archives: dict[str, ProductReleaseOs] = Field(default_factory=dict)
    plugins: dict[int, str | None] = Field(default_factory=dict)


class ProductsIndex(BaseModel):
    DEFAULT_FILE_NAME: ClassVar[str] = 'index.json'

    products: dict[str, ProductInfo] = Field(default_factory=dict)

    def write(self, directory: Path) -> Path:
        file = directory / self.DEFAULT_FILE_NAME
        logging.info(f'Generating metadata : {file}')
        try:
            with open(file, 'wt') as f:
                f.write(self.json(indent=4))
        except OSError as e:
            raise AppError(f'Could not write metadata {file}: {e}')
        return file


class Store(BaseModel):
    ARTEFACTS_DESTINATION: ClassVar[str] = 'artefacts'
    PRODUCTS_DESTINATION: ClassVar[str] = 'products'
    PLUGINS_DESTINATION: ClassVar[str] = 'plugins'

    destination: Path

    def artefacts_dir(self):
        return self.destination / self.ARTEFACTS_DESTINATION

    def products_dir(self):
        return self.artefacts_dir() / self.PRODUCTS_DESTINATION

    def plugins_dir(self):
        return self.artefacts_dir() / self.PLUGINS_DESTINATION

    def metadata_dir(self):
        return self.artefacts_dir()

    def relative_posix(self, path: Path) -> str:
        return path.relative_to(self.destination).as_posix()


class App:
    OPTION_CLEAN_UNKNOWN = '--clean-unknown'

    def __init__(self, argv: list[str] = None) -> None:
        self.args = self.parse_arguments(argv)
        level = logging.DEBUG if self.args.verbose else logging.INFO
        logging.basicConfig(level=level, format='%(levelname)s %(message)s')
        self.config = Config.load(self.args.config)
        self.store = Store(destination=self.args.dest)
        self.plugins: dict[int, JBPlugin] = {}
        self.plugins_updates: dict[int, list[JBPluginUpdate]] = {}
        self.cache = DiskCache() if self.args.cache_api else NoCache()
        self.api = JetBrainsApi(cache=self.cache, tracker=UrlTracker())
        self.unknown_file_tracker = UnknownFilesTracker()
        self.known_files: set[Path] = set()
        self.products_index = ProductsIndex()

    def parse_arguments(self, argv: list[str]):
        if argv is None:
            argv = sys.argv[1:]
        parser = argparse.ArgumentParser()
        parser.add_argument('-v', '--verbose', action='store_true')
        parser.add_argument('-c', '--config', default=Config.DEFAULT_FILE_NAME)
        parser.add_argument('-d', '--dest', default='.')
        parser.add_argument('--cache-api', action='store_true')
        parser.add_argument(self.OPTION_CLEAN_UNKNOWN, action='store_true')
        return parser.parse_args(argv)

    @staticmethod
    def get_product_release(product: JBProduct, version: str = None) -> JBProductRelease | None:
        if version is None:
            release = product.get_latest_release()
        else:
            release = product.get_release(version)
        if release is None:
            raise AppError(f'Version not found for {product.name}')
        return release

    def download_product_release_os_archive(self, link: str, os_dir: Path, size: int):
        file = self.api.download_file(link, os_dir)
        if file.stat().st_size != size:
            file.unlink()
            raise AppError(f'Downloaded {file} has the wrong size, and was removed')
        self.known_files.add(file)
        return file

    def download_product_release_os_hash(self, link: str, os_dir: Path, archive_file: Path):
        file = self.api.download_file(link, os_dir)
        if not is_digest_valid(archive_file, file):
            archive_file.unlink()
            raise AppError(f'Downloaded {archive_file} has the wrong hash, and was removed')
        logging.info(f'Valid {archive_file.name} found on disk')
        self.known_files.add(file)
        return file

    def download_product_release_os(self, info: JBProductReleaseDownloadInfo, id_os: str) -> ProductReleaseOs:
        os_dir = self.store.products_dir() / id_os
        self.known_files.add(os_dir)
        archive_file = self.download_product_release_os_archive(info.link, os_dir, info.size)
        hash_file = self.download_product_release_os_hash(info.checksum_link, os_dir, archive_file)
        return ProductReleaseOs(archive=self.store.relative_posix(archive_file),
                                hash=self.store.relative_posix(hash_file))

    @staticmethod
    def get_release_download_info(downloads: JBProductReleaseDownload, id_os: str) -> JBProductReleaseDownloadInfo:
        try:
            return getattr(downloads, id_os)
        except AttributeError:
            raise AppError(f'Unknown OS {id_os}')

    def download_product_release(self, release: JBProductRelease, config_os: list[str]) -> dict[str, ProductReleaseOs]:
        os_releases = {}
        for id_os in config_os:
            info = self.get_release_download_info(release.downloads, id_os)
            os_releases[id_os] = self.download_product_release_os(info, id_os)
        return os_releases

    def download_product(self, _id: str, config: ProductConfig) -> tuple[str, dict[str, ProductReleaseOs]]:
        product = self.api.get_product(_id)
        release = self.get_product_release(product, config.version)
        logging.info(f'Product {_id} is "{product.name}", and version {release.version} is build {release.build}')
        os_releases = self.download_product_release(release, config.os)
        return release.build, os_releases

    def is_plugin_update_compatible_with(self, update: JBPluginUpdate, product_tuple: tuple[int, ...]) -> bool:
        since = self.api.get_build_tuple(update.since)
        until = self.api.get_build_tuple(update.until)
        return self.api.is_build_between(since, product_tuple, until)

    def find_compatible_plugin_update(self, updates: list[JBPluginUpdate], product_build: str) -> JBPluginUpdate | None:
        product_tuple = self.api.get_build_tuple(product_build)
        for update in updates:
            if self.is_plugin_update_compatible_with(update, product_tuple):
                return update
        return None

    def download_plugin(self, plugin: JBPlugin, product_build: str) -> str | None:
        compatible = self.find_compatible_plugin_update(self.plugins_updates[plugin.id], product_build)
        if compatible is None:
            logging.warning(f'No matching plugin {plugin.name} version for product build {product_build}')
            return None
        logging.info(f'Plugin {plugin.name} version {compatible.version} matches {product_build}')
        file = self.api.download_plugin(compatible.id, self.store.plugins_dir())
        self.known_files.add(file)
        return self.store.relative_posix(file)

    def download_plugins(self, product_build: str) -> dict[int, str | None]:
        conf_plugins = (self.plugins[pid] for pid in self.config.plugins)
        # keep plugins for which a compatible version has not been found to notify preserve their incompatibility
        return {plugin.id: self.download_plugin(plugin, product_build) for plugin in conf_plugins}

    def process_configured_product(self, product_id: str, product_config: ProductConfig) -> None:
        build_id, os_releases = self.download_product(product_id, product_config)
        plugin_files = self.download_plugins(build_id)
        self.products_index.products[product_id] = ProductInfo(archives=os_releases, plugins=plugin_files)

    def process_configured_products(self) -> None:
        for product_id, product_config in self.config.products.items():
            logging.info(f'Processing {product_id}')
            self.process_configured_product(product_id, product_config)

    def load_configured_plugins_information(self):
        self.plugins = {pid: self.api.get_plugin(pid) for pid in self.config.plugins}
        logging.info(f'Found {len(self.plugins)} plugins in configuration')
        self.plugins_updates = {pid: self.api.get_plugin_updates_all(pid) for pid in self.config.plugins}

    def manage_unknown_files(self) -> None:
        logging.info(f'Found {len(self.known_files)} files linked to the configuration')
        unknown_files = self.unknown_file_tracker.get_unknown_files(self.store.artefacts_dir(), self.known_files)
        if len(unknown_files) > 0:
            self.unknown_file_tracker.write_unknown_files(unknown_files)
            logging.warning(f'Found {len(unknown_files)} unknown items in {self.store.artefacts_dir()}')
            logging.warning(f'List of unknown items has been saved in `{self.unknown_file_tracker.log_file}`')
            if self.args.clean_unknown:
                logging.info(f'Cleaning unknown files as requested...')
                self.unknown_file_tracker.clean_unknown_files(unknown_files)
            else:
                logging.warning(f'To remove the unknown items, restart with {self.OPTION_CLEAN_UNKNOWN}')
        logging.info(f'Management of known/unknown files complete')

    def manage_metadata(self):
        file = self.products_index.write(self.store.metadata_dir())
        self.known_files.add(file)

    def manage_url_tracker(self):
        file = self.api.url_tracker.write_tracked_url(self.store.metadata_dir())
        self.known_files.add(file)

    def reset(self):
        self.products_index.products.clear()
        self.known_files.clear()
        self.known_files.add(self.store.artefacts_dir())
        self.known_files.add(self.store.products_dir())
        self.known_files.add(self.store.plugins_dir())
        self.known_files.add(self.store.metadata_dir())

    def main(self):
        logging.info('Starting JetBrains product and plugins downloader...')
        self.reset()
        self.load_configured_plugins_information()
        self.process_configured_products()
        self.manage_metadata()
        self.manage_url_tracker()
        self.manage_unknown_files()
        logging.info('JetBrains product and plugins downloader finished.')


def main() -> None:
    try:
        App().main()
    except AppError as e:
        logging.error(e)


if __name__ == '__main__':
    main()
