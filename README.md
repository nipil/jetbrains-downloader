# jetbrains-downloader

Allows for easy product and plugin automatic downloads for offline use

## Setup with PIP and VENV

    sudo apt-get install -y --no-install-recommends python3-venv
    python3 -m venv .venv
    .venv/bin/pip3 install -r requirements.txt

    .venv/bin/python3 get.py

### Setup on Debian 12 with distribution packages

    sudo apt-get install -y --no-install-recommends python3-pydantic python3-urllib3 python3-yaml python3-requests python3-typing-extensions

    python3 get.py

## Docker

Docker files are provided to validate setup instructions and test in-situ.

- `Dockerfile.venv` to setup using `venv` and `pip` :

      docker build -f Dockerfile.venv -t jetbrains-downloader-venv .

- `Dockerfile.native` one using native distribution packages only :

      docker build -f Dockerfile.native -t jetbrains-downloader-native .

- Then run the application the same way, binding volumes to the host

      docker run --rm -v .:/app -t jetbrains-downloader-XXXXX --config /app/config.yaml --dest /app

## Usage

By default, `DEST` is a newly-created `artefacts` folder in the current directory.

    usage: get.py [-h] [-v] [-c CONFIG] [-d DEST] [--cache-api] [--clean-unknown]

    options:
      -h, --help            show this help message and exit
      -v, --verbose
      -c CONFIG, --config CONFIG
      -d DEST, --dest DEST
      --cache-api
      --clean-unknown

Notes :

- `--clean-unknown` is intended to prune old items when your versions evolve, in order to lower disk usage.
- `--cache-api` is only intended to speed up development, and saves the API replies to the `cache` folder.
    - Be careful when you use it to not accidentally use stale data
    - Delete `cache` folder when not working on code
    - Might make `url.json` incomplete as redirections are not seen when using cache !

## Sample configuration

Default YAML configuration file name is `config.yaml`. Some additional information :

- configuration is relative _to the current directory_
- only a few products are downloaded (by code name)
    - for each product the OS are listed to download installers (if os list is empty, nothing is downloaded)
    - if version is `null`, then the latest version found on the website is downloaded (yaml is **not** updated)
- the listed plugins are attempted for **each** listed product
    - plugins may be downloaded in multiple versions to match the build requirements of the product
    - requested plugins may not be downloaded if no version satisfies the requirements for the product

Example configuration :

    ---
    products:
      IIC: # IntelliJ IDEA Community Edition
        version: 2024.3.2.2
        os:
          - windows
          - linux
      IIU: # IntelliJ IDEA Ultimate
        version: 2024.3.2.2
        os:
          - linux
      PCP: # PyCharm Professional Edition
        version: 2024.3.2
        os:
          - linux
      PS: # PhpStorm
        version: 2024.3.2.1
        os: [ ]
      RR: # RustRover
        version: 2024.3.4
        os:
          - linux
    plugins:   # https://plugins.jetbrains.com/
      - 7157   # https://plugins.jetbrains.com/plugin/7157-javadoc
      - 7177   # https://plugins.jetbrains.com/plugin/7177-file-watchers
      - 7448   # https://plugins.jetbrains.com/plugin/7448-zero-width-characters-locator
      - 7793   # https://plugins.jetbrains.com/plugin/7793-markdown
      - 7808   # https://plugins.jetbrains.com/plugin/7808-terraform-and-hcl
      - 8215   # https://plugins.jetbrains.com/plugin/8215-youtrack-integration
      - 10249  # https://plugins.jetbrains.com/plugin/10249-powershell
      - 10581  # https://plugins.jetbrains.com/plugin/10581-go-template
      - 11070  # https://plugins.jetbrains.com/plugin/11070-unit-file-support-systemd-/versions/stable
      - 12175  # https://plugins.jetbrains.com/plugin/12175-grazie-lite
      - 12394  # https://plugins.jetbrains.com/plugin/12394-kubernetes-runtime-configuration
      - 13122  # https://plugins.jetbrains.com/plugin/13122-shell-script
      - 13126  # https://plugins.jetbrains.com/plugin/13126-yaml
      - 13308  # https://plugins.jetbrains.com/plugin/13308-indent-rainbow
      - 16136  # https://plugins.jetbrains.com/plugin/16136-grazie-pro
      - 18271  # https://plugins.jetbrains.com/plugin/18271-unicorn-progress-bar

## Sample results on disk

Product installers are downloaded along with their hash verification file, and verified upon completion.

    $ tree --filesfirst artefacts

    artefacts
    |-- index.json
    |-- url.json
    |-- plugins
    |   |-- Indent_Rainbow-2.2.0-signed.zip
    |   |-- PowerShell-2.8.0.zip
    |   |-- UnicornProgressBar-1.1.4.zip
    |   |-- ZeroLengthRadar-0.95.zip
    |   |-- fileWatcher-243.23654.19.zip
    |   |-- go-template-243.21565.122.zip
    |   |-- grazie-pro-0.3.359.zip
    |   |-- intellij-javadocs-4.1.3.zip
    |   |-- intellij-k8s-runtime-config-1.4.1.zip
    |   |-- sh-243.22562.53.zip
    |   |-- systemdUnitFilePlugin-242.250115.172.zip
    |   |-- terraform-243.23654.44.zip
    |   |-- yaml-243.23654.189.zip
    |   `-- ytplugin-2024.2.123.zip
    `-- products
        |-- linux
        |   |-- RustRover-2024.3.4.tar.gz
        |   |-- RustRover-2024.3.4.tar.gz.sha256
        |   |-- ideaIC-2024.3.2.2.tar.gz
        |   |-- ideaIC-2024.3.2.2.tar.gz.sha256
        |   |-- ideaIU-2024.3.2.2.tar.gz
        |   |-- ideaIU-2024.3.2.2.tar.gz.sha256
        |   |-- pycharm-professional-2024.3.2.tar.gz
        |   `-- pycharm-professional-2024.3.2.tar.gz.sha256
        `-- windows
            |-- ideaIC-2024.3.2.2.exe
            `-- ideaIC-2024.3.2.2.exe.sha256

## Sample tracked URL file

An `url.json` metadata file is generated with all the URL seen during processing :

- the requested URL are logged
- the final URL are logged too (after) redirects
- same for the hostnames
- **WARNING**: if _multiple_ redirects are done, the intermediary urls will _not_ be logged

This allows precise and easy URL generation, for inclusion in secure web gateways whitelists.

Sample output :

    {
        "request_hostname": [
            "data.services.jetbrains.com",
            "download.jetbrains.com",
            "plugins.jetbrains.com"
        ],
        "response_hostname": [
            "download-cdn.jetbrains.com",
            "downloads.marketplace.jetbrains.com"
        ],
        "request_url": [
            "https://data.services.jetbrains.com/products?code=IIC&release.type=release",
            ...
            "https://download.jetbrains.com/idea/ideaIC-2024.3.2.2.exe",
            ...
            "https://plugins.jetbrains.com/api/plugins/10249",
            ...
        ],
        "response_url": [
            "https://download-cdn.jetbrains.com/idea/ideaIC-2024.3.2.2.exe",
            ...
            "https://downloads.marketplace.jetbrains.com/files/10249/621620/PowerShell-2.8.0.zip?updateId=621620&pluginId=10249&family=INTELLIJ",
            ...
        ]
    }

## Sample metadata file

An `index.json` metadata file is generated for downloaded products, in order to :

- to be able to script any offline/air-gapped installation more easily
- to be able to link present files on disk versus desired products/plugins

Content looks like the following :

    {
        "products": {
            "IIC": {
                "archives": {
                    "windows": {
                        "archive": "artefacts/products/windows/ideaIC-2024.3.2.2.exe",
                        "hash": "artefacts/products/windows/ideaIC-2024.3.2.2.exe.sha256"
                    },
                    "linux": {
                        "archive": "artefacts/products/linux/ideaIC-2024.3.2.2.tar.gz",
                        "hash": "artefacts/products/linux/ideaIC-2024.3.2.2.tar.gz.sha256"
                    }
                },
                "plugins": {
                    "7157": "artefacts/plugins/intellij-javadocs-4.1.3.zip",
                    ...
                }
            },
            "IIU": {
                ...
            },
            ...
        }
    }

## Sample unknown file

The `artefacts` folder is scanned to be kept up-to-date with the configuration.

An information file named `unknown.txt` lists every file and folder which does not map to the configuration.

The `--clean-unknown` option can be used to clean these unknown files automatically, but it must be explicit.

## Sample logging output

    INFO Starting JetBrains product and plugins downloader...
    INFO Found 16 plugins in configuration
    INFO Found 22 releases for plugin id 7157
    INFO Found 481 releases for plugin id 7177
    INFO Found 5 releases for plugin id 7448
    INFO Found 257 releases for plugin id 7793
    INFO Found 310 releases for plugin id 7808
    INFO Found 95 releases for plugin id 8215
    INFO Found 30 releases for plugin id 10249
    INFO Found 403 releases for plugin id 10581
    INFO Found 82 releases for plugin id 11070
    INFO Found 298 releases for plugin id 12175
    INFO Found 21 releases for plugin id 12394
    INFO Found 204 releases for plugin id 13122
    INFO Found 206 releases for plugin id 13126
    INFO Found 22 releases for plugin id 13308
    INFO Found 238 releases for plugin id 16136
    INFO Found 2 releases for plugin id 18271
    INFO Processing IIC
    INFO Product IIC is "IntelliJ IDEA Community Edition", and version 2024.3.2.2 is build 243.23654.189
    INFO Valid ideaIC-2024.3.2.2.exe found on disk
    INFO Valid ideaIC-2024.3.2.2.tar.gz found on disk
    INFO Plugin JavaDoc version 4.1.3 matches 243.23654.189
    INFO Plugin File Watchers version 243.23654.19 matches 243.23654.189
    INFO Plugin Zero Width Characters locator version 0.95 matches 243.23654.189
    WARNING No matching plugin Markdown version for product build 243.23654.189
    INFO Plugin Terraform and HCL version 243.23654.44 matches 243.23654.189
    INFO Plugin YouTrack Integration version 2024.2.123 matches 243.23654.189
    INFO Plugin PowerShell version 2.8.0 matches 243.23654.189
    INFO Plugin Go Template version 243.21565.122 matches 243.23654.189
    INFO Plugin Unit File Support (systemd) version 242.250115.172 matches 243.23654.189
    WARNING No matching plugin Grazie Lite version for product build 243.23654.189
    INFO Plugin Kubernetes Runtime Configuration version 1.4.1 matches 243.23654.189
    INFO Plugin Shell Script version 243.22562.53 matches 243.23654.189
    INFO Plugin YAML version 243.23654.189 matches 243.23654.189
    INFO Plugin Indent Rainbow version 2.2.0 matches 243.23654.189
    INFO Plugin Grazie Pro version 0.3.359 matches 243.23654.189
    INFO Plugin Unicorn Progress Bar version 1.1.4 matches 243.23654.189
    INFO Processing IIU
    INFO Product IIU is "IntelliJ IDEA Ultimate", and version 2024.3.2.2 is build 243.23654.189
    INFO Valid ideaIU-2024.3.2.2.tar.gz found on disk
    INFO Plugin JavaDoc version 4.1.3 matches 243.23654.189
    INFO Plugin File Watchers version 243.23654.19 matches 243.23654.189
    INFO Plugin Zero Width Characters locator version 0.95 matches 243.23654.189
    WARNING No matching plugin Markdown version for product build 243.23654.189
    INFO Plugin Terraform and HCL version 243.23654.44 matches 243.23654.189
    INFO Plugin YouTrack Integration version 2024.2.123 matches 243.23654.189
    INFO Plugin PowerShell version 2.8.0 matches 243.23654.189
    INFO Plugin Go Template version 243.21565.122 matches 243.23654.189
    INFO Plugin Unit File Support (systemd) version 242.250115.172 matches 243.23654.189
    WARNING No matching plugin Grazie Lite version for product build 243.23654.189
    INFO Plugin Kubernetes Runtime Configuration version 1.4.1 matches 243.23654.189
    INFO Plugin Shell Script version 243.22562.53 matches 243.23654.189
    INFO Plugin YAML version 243.23654.189 matches 243.23654.189
    INFO Plugin Indent Rainbow version 2.2.0 matches 243.23654.189
    INFO Plugin Grazie Pro version 0.3.359 matches 243.23654.189
    INFO Plugin Unicorn Progress Bar version 1.1.4 matches 243.23654.189
    INFO Processing PCP
    INFO Product PCP is "PyCharm Professional Edition", and version 2024.3.2 is build 243.23654.177
    INFO Valid pycharm-professional-2024.3.2.tar.gz found on disk
    INFO Plugin JavaDoc version 4.1.3 matches 243.23654.177
    INFO Plugin File Watchers version 243.23654.19 matches 243.23654.177
    INFO Plugin Zero Width Characters locator version 0.95 matches 243.23654.177
    WARNING No matching plugin Markdown version for product build 243.23654.177
    INFO Plugin Terraform and HCL version 243.23654.44 matches 243.23654.177
    INFO Plugin YouTrack Integration version 2024.2.123 matches 243.23654.177
    INFO Plugin PowerShell version 2.8.0 matches 243.23654.177
    INFO Plugin Go Template version 243.21565.122 matches 243.23654.177
    INFO Plugin Unit File Support (systemd) version 242.250115.172 matches 243.23654.177
    WARNING No matching plugin Grazie Lite version for product build 243.23654.177
    INFO Plugin Kubernetes Runtime Configuration version 1.4.1 matches 243.23654.177
    INFO Plugin Shell Script version 243.22562.53 matches 243.23654.177
    INFO Plugin YAML version 243.23654.189 matches 243.23654.177
    INFO Plugin Indent Rainbow version 2.2.0 matches 243.23654.177
    INFO Plugin Grazie Pro version 0.3.359 matches 243.23654.177
    INFO Plugin Unicorn Progress Bar version 1.1.4 matches 243.23654.177
    INFO Processing PS
    INFO Product PS is "PhpStorm", and version 2024.3.2.1 is build 243.23654.168
    INFO Plugin JavaDoc version 4.1.3 matches 243.23654.168
    INFO Plugin File Watchers version 243.23654.19 matches 243.23654.168
    INFO Plugin Zero Width Characters locator version 0.95 matches 243.23654.168
    WARNING No matching plugin Markdown version for product build 243.23654.168
    INFO Plugin Terraform and HCL version 243.23654.44 matches 243.23654.168
    INFO Plugin YouTrack Integration version 2024.2.123 matches 243.23654.168
    INFO Plugin PowerShell version 2.8.0 matches 243.23654.168
    INFO Plugin Go Template version 243.21565.122 matches 243.23654.168
    INFO Plugin Unit File Support (systemd) version 242.250115.172 matches 243.23654.168
    WARNING No matching plugin Grazie Lite version for product build 243.23654.168
    INFO Plugin Kubernetes Runtime Configuration version 1.4.1 matches 243.23654.168
    INFO Plugin Shell Script version 243.22562.53 matches 243.23654.168
    INFO Plugin YAML version 243.23654.189 matches 243.23654.168
    INFO Plugin Indent Rainbow version 2.2.0 matches 243.23654.168
    INFO Plugin Grazie Pro version 0.3.359 matches 243.23654.168
    INFO Plugin Unicorn Progress Bar version 1.1.4 matches 243.23654.168
    INFO Processing RR
    INFO Product RR is "RustRover", and version 2024.3.4 is build 243.23654.180
    INFO Valid RustRover-2024.3.4.tar.gz found on disk
    INFO Plugin JavaDoc version 4.1.3 matches 243.23654.180
    INFO Plugin File Watchers version 243.23654.19 matches 243.23654.180
    INFO Plugin Zero Width Characters locator version 0.95 matches 243.23654.180
    WARNING No matching plugin Markdown version for product build 243.23654.180
    INFO Plugin Terraform and HCL version 243.23654.44 matches 243.23654.180
    INFO Plugin YouTrack Integration version 2024.2.123 matches 243.23654.180
    INFO Plugin PowerShell version 2.8.0 matches 243.23654.180
    INFO Plugin Go Template version 243.21565.122 matches 243.23654.180
    INFO Plugin Unit File Support (systemd) version 242.250115.172 matches 243.23654.180
    WARNING No matching plugin Grazie Lite version for product build 243.23654.180
    INFO Plugin Kubernetes Runtime Configuration version 1.4.1 matches 243.23654.180
    INFO Plugin Shell Script version 243.22562.53 matches 243.23654.180
    INFO Plugin YAML version 243.23654.189 matches 243.23654.180
    INFO Plugin Indent Rainbow version 2.2.0 matches 243.23654.180
    INFO Plugin Grazie Pro version 0.3.359 matches 243.23654.180
    INFO Plugin Unicorn Progress Bar version 1.1.4 matches 243.23654.180
    INFO Generating metadata : artefacts\index.json
    INFO Writing tracked url to artefacts\url.json
    INFO Found 31 files linked to the configuration
    WARNING Found 1 unknown items in artefacts
    WARNING List of unknown items has been saved in `unknown.txt`
    WARNING To remove the unknown items, restart with --clean-unknown
    INFO Management of known/unknown files complete
    INFO JetBrains product and plugins downloader finished.
