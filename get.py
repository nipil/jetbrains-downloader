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

import requests
import yaml
from pydantic import BaseModel, Field, validator
from pydantic.networks import HttpUrl
from requests import Request, Session, PreparedRequest


class AppError(Exception):
    pass


def download_file(url: str, directory: Path, *, params: dict = None) -> Path:
    if params is None:
        params = {}
    logging.debug(f'Downloading {url} to {directory}')
    directory.mkdir(parents=True, exist_ok=True)
    try:
        with (requests.get(url, stream=True, params=params) as response):
            url = response.request.url
            file = os.path.basename(urlparse(url).path)
            target = directory / file
            if target.exists():
                logging.debug(f'File {file} already exists: skipping download')
                return target
            logging.info(f'Downloading {file}...')
            with open(target, 'wb') as f:
                # noinspection PyTypeChecker
                shutil.copyfileobj(response.raw, f)  # type hint issue for f
    except Exception as e:
        target.unlink(missing_ok=True)
        raise AppError(f'Failed to download {url}, eventual file {file} was purged : {e}')
    return target


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
    def load(cls, config_file: Path) -> Self:
        try:
            with open(config_file, 'rb') as f:
                config = yaml.safe_load(f)
                return Config(**config)
        except OSError as e:
            raise AppError(f'Failed to load {config_file}: {e}')


class JetBrainsProductReleaseDownloadInfo(BaseModel):
    link: HttpUrl
    size: int
    checksum_link: HttpUrl = Field(alias='checksumLink')


class JetBrainsProductReleaseType(Enum):
    release = 'release'


class JetBrainsProductReleaseDownload(BaseModel):
    # some release are missing platforms
    linux: JetBrainsProductReleaseDownloadInfo = Field(default=None)
    windows: JetBrainsProductReleaseDownloadInfo = Field(default=None)


class JetBrainsProductRelease(BaseModel):
    date: datetime.date
    type: JetBrainsProductReleaseType
    version: str
    build: str
    downloads: JetBrainsProductReleaseDownload


class JetBrainsProduct(BaseModel):
    code: str
    name: str
    releases: list[JetBrainsProductRelease]

    def get_release(self, version: str) -> JetBrainsProductRelease | None:
        return next((release for release in self.releases if release.version == version), None)

    def get_latest_release(self) -> JetBrainsProductRelease | None:
        try:
            return self.releases[0]
        except IndexError:
            return None


class JetBrainsPlugin(BaseModel):
    id: int
    name: str
    family: str


class JetBrainsPluginUpdateBuildValidator:
    # Valid : "", "123", "123.*", "123.456", "123.456.*", "123.456.789"
    RE = re.compile(r'^(|\d+|\d+\.(\d+|\*)|\d+\.\d+\.(\d+|\*))$')

    @classmethod
    def is_valid(cls, value: str) -> str:
        if cls.RE.fullmatch(value) is None:
            raise ValueError(f'Build string `{value}` does not match {cls.RE.pattern} but does not : ')
        return value


class JetBrainsPluginUpdate(BaseModel):
    id: int
    version: str
    timestamp_ms: int = Field(alias='cdate')
    file: Path
    since: str = None
    until: str = None

    _since_validator = validator('since', allow_reuse=True)(JetBrainsPluginUpdateBuildValidator.is_valid)
    _until_validator = validator('until', allow_reuse=True)(JetBrainsPluginUpdateBuildValidator.is_valid)


class JetBrainsApi:
    DATA_URL = 'https://data.services.jetbrains.com'
    PLUGIN_URL = 'https://plugins.jetbrains.com'

    def __init__(self, *, cache=None):
        self.session = Session()
        self.cache = cache

    def do_cached_query(self, request: PreparedRequest) -> dict:
        try:
            data = self.cache.read(request.url)
        except KeyError:
            data = self.session.send(request).json()
            self.cache.put(request.url, data)
        return data

    def get_product(self, product_id: str) -> JetBrainsProduct:
        params = {"code": product_id, "release.type": JetBrainsProductReleaseType.release.value}
        request = Request('GET', f'{self.DATA_URL}/products', params=params).prepare()
        data = self.do_cached_query(request)
        if not isinstance(data, list) or len(data) != 1:
            raise AppError(f'Product information for {product_id} is not in a recognized format')
        return JetBrainsProduct(**data[0])

    def get_plugin(self, plugin_id: int) -> JetBrainsPlugin:
        req = Request('GET', f'{self.PLUGIN_URL}/api/plugins/{plugin_id}').prepare()
        data = self.do_cached_query(req)
        if not isinstance(data, dict):
            raise AppError(f'Plugin information for {plugin_id} is not in a recognized format')
        return JetBrainsPlugin(**data)

    def get_plugin_updates(self, plugin_id: int, page: int, page_size: int) -> list[JetBrainsPluginUpdate]:
        params = {'page': page, 'size': page_size}
        req = Request('GET', f'{self.PLUGIN_URL}/api/plugins/{plugin_id}/updates', params=params).prepare()
        data = self.do_cached_query(req)
        if not isinstance(data, list):
            raise AppError(f'Plugin updates for {plugin_id} is not in a recognized format')
        return [JetBrainsPluginUpdate(**item) for item in data]

    def get_plugin_updates_all(self, plugin_id: int, page_size: int = 100) -> list[JetBrainsPluginUpdate]:
        page = 0
        updates = []
        while True:
            items = self.get_plugin_updates(plugin_id, page, page_size)
            logging.debug(f'Updates received: {len(items)}')
            updates.extend(items)
            if len(items) < page_size:
                break
            page += 1
        return updates

    def download_plugin(self, plugin_update_id: int, directory: Path) -> Path:
        params = {'rel': True, 'updateId': plugin_update_id}
        return download_file(f'{self.PLUGIN_URL}/plugin/download', directory, params=params)


class Cache:

    def read(self, key: str) -> Any:
        raise NotImplementedError()

    def put(self, key: str, value: Any) -> None:
        raise NotImplementedError()


class NoCache(Cache):

    def __init__(self) -> None:
        pass

    def read(self, key: str) -> Any:
        raise KeyError(key)

    def put(self, key: str, value: Any) -> None:
        pass


class DiskCache(Cache):

    def __init__(self, destination: Path, *, key_hash_algorithm='sha256') -> None:
        self.destination = destination
        self.algorithm = key_hash_algorithm
        self.destination.mkdir(parents=True, exist_ok=True)

    def file_key(self, key: str) -> str:
        h = hashlib.new(self.algorithm)
        h.update(key.encode())
        return h.hexdigest()

    def file_path(self, key: str) -> Path:
        return self.destination / self.file_key(key)

    def read(self, key: str) -> Any:
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
        except OSError:
            raise AppError(f'Could not write disk cache for key {key}')
        logging.debug(f'Caching flush for {key} at {file}')


class App:
    DEFAULT_DESTINATION = 'artefacts'
    PRODUCTS_DESTINATION = 'products'
    PLUGINS_DESTINATION = 'plugins'
    CACHE_DESTINATION = 'cache'
    UNKNOWN_FILES = 'unknown.txt'
    OPTION_CLEAN_UNKNOWN = '--clean-unknown'

    def __init__(self, argv: list[str] = None) -> None:
        if argv is None:
            argv = sys.argv[1:]
        parser = argparse.ArgumentParser()
        parser.add_argument('-v', '--verbose', action='store_true')
        parser.add_argument('-c', '--config', default=Config.DEFAULT_FILE_NAME)
        parser.add_argument('-d', '--dest', default=App.DEFAULT_DESTINATION)
        parser.add_argument('--cache-api', action='store_true')
        parser.add_argument(self.OPTION_CLEAN_UNKNOWN, action='store_true')
        self.args = parser.parse_args(argv)
        level = logging.DEBUG if self.args.verbose else logging.INFO
        logging.basicConfig(level=level, format='%(levelname)s %(message)s')
        self.args.dest = Path(self.args.dest)
        self.config = Config.load(Path(self.args.config))
        self.plugins: dict[int, JetBrainsPlugin] = {}
        self.plugins_updates: dict[int, list[JetBrainsPluginUpdate]] = {}
        if self.args.cache_api:
            logging.debug(f'Caching from disk at "{self.CACHE_DESTINATION}"')
            self.cache = DiskCache(Path(self.CACHE_DESTINATION))
        else:
            self.cache = NoCache()
        self.api = JetBrainsApi(cache=self.cache)

    def get_products_destination(self):
        return self.args.dest / self.PRODUCTS_DESTINATION

    def get_plugins_destination(self):
        return self.args.dest / self.PLUGINS_DESTINATION

    def get_metadata_destination(self):
        return self.args.dest

    @staticmethod
    def get_hash_function(identifier: str) -> Callable:
        match identifier:
            case 'sha256':
                return hashlib.sha256
        raise AppError(f'Unhandled hash identifier {identifier}')

    @staticmethod
    def get_product_release(product: JetBrainsProduct, version: str = None) -> JetBrainsProductRelease | None:
        if version is None:
            release = product.get_latest_release()
        else:
            release = product.get_release(version)
        if release is None:
            raise AppError(f'Version not found for {product.name}')
        return release

    def download_product_info(self, info: JetBrainsProductReleaseDownloadInfo) -> list[Path]:
        products_dir = self.get_products_destination()
        product_file = download_file(str(info.link), products_dir)
        if product_file.stat().st_size != info.size:
            product_file.unlink()
            raise AppError(f'Downloaded {product_file} has the wrong size, and was removed')
        hash_file = download_file(str(info.checksum_link), products_dir)
        if not is_digest_valid(product_file, hash_file):
            product_file.unlink()
            raise AppError(f'Downloaded {product_file} has the wrong hash, and was removed')
        logging.info(f'Valid {product_file.name} found on disk')
        return [product_file, hash_file]

    def download_product_release_os(self, downloads: JetBrainsProductReleaseDownload, id_os: str) -> list[Path]:
        try:
            info: JetBrainsProductReleaseDownloadInfo = getattr(downloads, id_os)
        except AttributeError:
            raise AppError(f'Unknown OS {id_os}')
        return self.download_product_info(info)

    def download_product_release(self, release: JetBrainsProductRelease, config_os: list[str]) -> list[Path]:
        product_files = []
        for id_os in config_os:
            files = self.download_product_release_os(release.downloads, id_os)
            product_files.extend(files)
        return product_files

    def download_product(self, _id: str, config: ProductConfig) -> tuple[str, list[Path]]:
        product = self.api.get_product(_id)
        release = self.get_product_release(product, config.version)
        logging.info(f'Product {_id} is "{product.name}", and version {release.version} is build {release.build}')
        files = self.download_product_release(release, config.os)
        return release.build, files

    @staticmethod
    def is_build_compatible(target: tuple, since: tuple, until: tuple) -> bool:
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

    @staticmethod
    def get_build_tuple_from_build_string(build: str) -> tuple | None:
        return tuple(int(x) for x in build.split('.') if x.strip() not in ('*', ''))

    def is_plugin_update_compatible_with(self, update: JetBrainsPluginUpdate, product_tuple: tuple[int, ...]) -> bool:
        since = self.get_build_tuple_from_build_string(update.since)
        until = self.get_build_tuple_from_build_string(update.until)
        return self.is_build_compatible(product_tuple, since, until)

    def find_compatible_plugin_update(self, updates: list, product_tuple: tuple) -> JetBrainsPluginUpdate | None:
        for update in updates:
            if self.is_plugin_update_compatible_with(update, product_tuple):
                return update
        return None

    def download_plugin(self, plugin: JetBrainsPlugin, product_build: str) -> Path | None:
        product_tuple = self.get_build_tuple_from_build_string(product_build)
        updates = self.plugins_updates[plugin.id]
        compatible = self.find_compatible_plugin_update(updates, product_tuple)
        if compatible is None:
            logging.warning(f'No matching plugin {plugin.name} version for product build {product_build}')
            return None
        logging.info(f'Found matching plugin {plugin.name} version {compatible.version}')
        folder = self.get_plugins_destination()
        return self.api.download_plugin(compatible.id, folder)

    def download_plugins(self, product_build: str) -> list[Path]:
        plugin_files = []
        for plugin_id in self.config.plugins:
            info = self.plugins[plugin_id]
            file = self.download_plugin(info, product_build)
            if file is None:
                continue
            plugin_files.append(file)
        return plugin_files

    def create_product_metadata(self, product_id: str, product_files: list[Path], plugin_files: list[Path]) -> Path:
        logging.info(f'Generating metadata for product {product_id}')
        metadata_file = f'{product_id.lower()}.json'
        metadata_path = self.get_metadata_destination() / metadata_file
        product_files = [file.name for file in product_files]
        plugin_files = [file.name for file in plugin_files]
        data = {"products": product_files, "plugins": plugin_files}
        try:
            with open(metadata_path, 'wt') as f:
                f.write(json.dumps(data, indent=4))
        except OSError:
            raise AppError(f'Could not metadata {metadata_path}')
        return metadata_path

    def process_configured_product(self, product_id: str, product_config: ProductConfig) -> list[Path]:
        build_id, product_files = self.download_product(product_id, product_config)
        plugin_files = self.download_plugins(build_id)
        metadata_file = self.create_product_metadata(product_id, product_files, plugin_files)
        return plugin_files + product_files + [metadata_file]

    def process_configured_products(self) -> list[Path]:
        all_files = [self.get_products_destination(), self.get_plugins_destination(), self.get_metadata_destination()]
        for product_id, product_config in self.config.products.items():
            logging.info(f'Processing {product_id}')
            files = self.process_configured_product(product_id, product_config)
            all_files.extend(files)
        return all_files

    def load_configured_plugins_information(self):
        self.plugins.clear()
        self.plugins_updates.clear()
        for plugin_id in self.config.plugins:
            logging.debug(f'Getting plugin {plugin_id} informations...')
            plugin = self.api.get_plugin(plugin_id)
            self.plugins[plugin_id] = plugin
            updates = self.api.get_plugin_updates_all(plugin_id)
            updates.sort(key=lambda x: x.timestamp_ms, reverse=True)
            self.plugins_updates[plugin_id] = updates
            logging.info(f'Found {len(updates)} releases of plugin "{plugin.name}" (id={plugin_id})')

    def get_unknown_files(self, known_files: list[Path]) -> list[Path]:
        known_files = set(known_files)
        unknown_files = list()
        for entry in self.args.dest.rglob('*'):
            if entry not in known_files:
                item = (not entry.is_dir(), entry)
                unknown_files.append(item)
        unknown_files.sort(reverse=True)
        return [entry[1] for entry in unknown_files]

    def write_unknown_files(self, unknown_files: list[Path]) -> None:
        try:
            with open(self.UNKNOWN_FILES, "wt") as f:
                for entry in unknown_files:
                    f.write(f'{entry}\n')
        except OSError as e:
            raise AppError(f'Could not write list of unknown files : {e}')

    @staticmethod
    def clean_unknown_files(unknown_files: list[Path]) -> None:
        for entry in unknown_files:
            try:
                logging.info(f'Removing {entry}')
                if entry.is_dir():
                    entry.rmdir()
                else:
                    entry.unlink(missing_ok=True)
            except OSError as e:
                logging.warning(f'Could not remove unknown file {entry} : {e}')

    def manage_unknown_files(self, known_files: list[Path]) -> None:
        logging.info(f'Found {len(known_files)} files linked to the configuration')
        unknown_files = self.get_unknown_files(known_files)
        if len(unknown_files) > 0:
            self.write_unknown_files(unknown_files)
            logging.warning(f'Found {len(unknown_files)} unknown files or directories in {self.args.dest}')
            logging.warning(f'List of unknown items has been saved in `{self.UNKNOWN_FILES}` for information')
            if self.args.clean_unknown:
                logging.info(f'Cleaning unknown files as requested...')
                self.clean_unknown_files(unknown_files)
            else:
                logging.warning(f'To remove the unknown items, restart with {self.OPTION_CLEAN_UNKNOWN}')
        logging.info(f'Management of known/unknown files complete')

    def main(self):
        logging.info('Starting JetBrains product and plugins downloader...')
        self.load_configured_plugins_information()
        known_files = self.process_configured_products()
        self.manage_unknown_files(known_files)
        logging.info('JetBrains product and plugins downloader finished.')


def main() -> None:
    try:
        App().main()
    except AppError as e:
        logging.error(e)


if __name__ == '__main__':
    main()
