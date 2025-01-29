# jetbrains-downloader

Allows for easy product and plugin automatic downloads for offline use

## Install on Debian

    sudo apt-get install -y --no-install-recommends python3-venv
    python3 -m venv .venv
    .venv/bin/pip3 install -r requirements.txt
    .venv/bin/python3 get.py

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
- `--cache-api` is only intended to speed up development, and saves the API replies to the `cache` folder. \
  Be careful when you use it to not accidentally use stale data. Delete `cache` folder when not working on code.

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

    $ tree  artefacts/  --filesfirst
    artefacts/
    ├── iic.json
    ├── iiu.json
    ├── pcp.json
    ├── ps.json
    ├── rr.json
    ├── plugins
    │   ├── Indent_Rainbow-2.2.0-signed.zip
    │   ├── PowerShell-2.8.0.zip
    │   ├── UnicornProgressBar-1.1.4.zip
    │   ├── ZeroLengthRadar-0.95.zip
    │   ├── fileWatcher-243.23654.19.zip
    │   ├── go-template-243.21565.122.zip
    │   ├── grazie-pro-0.3.359.zip
    │   ├── intellij-javadocs-4.1.3.zip
    │   ├── intellij-k8s-runtime-config-1.4.1.zip
    │   ├── sh-243.22562.53.zip
    │   ├── systemdUnitFilePlugin-242.250115.172.zip
    │   ├── terraform-243.23654.44.zip
    │   ├── yaml-243.23654.189.zip
    │   └── ytplugin-2024.2.123.zip
    └── products
        ├── RustRover-2024.3.4.tar.gz
        ├── RustRover-2024.3.4.tar.gz.sha256
        ├── ideaIC-2024.3.2.2.exe
        ├── ideaIC-2024.3.2.2.exe.sha256
        ├── ideaIC-2024.3.2.2.tar.gz
        ├── ideaIC-2024.3.2.2.tar.gz.sha256
        ├── ideaIU-2024.3.2.2.tar.gz
        ├── ideaIU-2024.3.2.2.tar.gz.sha256
        ├── pycharm-professional-2024.3.2.tar.gz
        └── pycharm-professional-2024.3.2.tar.gz.sha256

## Sample metadata file

Metadata files are produced for each product, in order  :

- to be able to script any offline/air-gapped installation more easily
- to be able to link present files on disk versus desired products/plugins

One file per product is produced, with a content similar to the following :

    {
        "products": [
            "ideaIC-2024.3.2.2.exe",
            "ideaIC-2024.3.2.2.exe.sha256",
            "ideaIC-2024.3.2.2.tar.gz",
            "ideaIC-2024.3.2.2.tar.gz.sha256"
        ],
        "plugins": [
            "intellij-javadocs-4.1.3.zip",
            "fileWatcher-243.23654.19.zip",
            "ZeroLengthRadar-0.95.zip",
            "terraform-243.23654.44.zip",
            "ytplugin-2024.2.123.zip",
            "PowerShell-2.8.0.zip",
            "go-template-243.21565.122.zip",
            "systemdUnitFilePlugin-242.250115.172.zip",
            "intellij-k8s-runtime-config-1.4.1.zip",
            "sh-243.22562.53.zip",
            "yaml-243.23654.189.zip",
            "Indent_Rainbow-2.2.0-signed.zip",
            "grazie-pro-0.3.359.zip",
            "UnicornProgressBar-1.1.4.zip"
        ]
    }

## Sample unknown file

The `artefacts` folder is scanned to be kept up-to-date with the configuration.

An information file named `unknown.txt` lists every file and folder which does not map to the configuration.

The `--clean-unknown` option can be used to clean these unknown files automatically, but it must be explicit.

## Sample logging output

    INFO Starting JetBrains product and plugins downloader...
    INFO Found 22 releases of plugin "JavaDoc" (id=7157)
    INFO Found 481 releases of plugin "File Watchers" (id=7177)
    INFO Found 5 releases of plugin "Zero Width Characters locator" (id=7448)
    INFO Found 257 releases of plugin "Markdown" (id=7793)
    INFO Found 310 releases of plugin "Terraform and HCL" (id=7808)
    INFO Found 95 releases of plugin "YouTrack Integration" (id=8215)
    INFO Found 30 releases of plugin "PowerShell" (id=10249)
    INFO Found 403 releases of plugin "Go Template" (id=10581)
    INFO Found 82 releases of plugin "Unit File Support (systemd)" (id=11070)
    INFO Found 298 releases of plugin "Grazie Lite" (id=12175)
    INFO Found 21 releases of plugin "Kubernetes Runtime Configuration" (id=12394)
    INFO Found 204 releases of plugin "Shell Script" (id=13122)
    INFO Found 206 releases of plugin "YAML" (id=13126)
    INFO Found 22 releases of plugin "Indent Rainbow" (id=13308)
    INFO Found 238 releases of plugin "Grazie Pro" (id=16136)
    INFO Found 2 releases of plugin "Unicorn Progress Bar" (id=18271)
    INFO Processing IIC
    INFO Product IIC is "IntelliJ IDEA Community Edition", and version 2024.3.2.2 is build 243.23654.189
    INFO Valid ideaIC-2024.3.2.2.exe found on disk
    INFO Valid ideaIC-2024.3.2.2.tar.gz found on disk
    INFO Found matching plugin JavaDoc version 4.1.3
    INFO Found matching plugin File Watchers version 243.23654.19
    INFO Found matching plugin Zero Width Characters locator version 0.95
    WARNING No matching plugin Markdown version for product build 243.23654.189
    INFO Found matching plugin Terraform and HCL version 243.23654.44
    INFO Found matching plugin YouTrack Integration version 2024.2.123
    INFO Found matching plugin PowerShell version 2.8.0
    INFO Found matching plugin Go Template version 243.21565.122
    INFO Found matching plugin Unit File Support (systemd) version 242.250115.172
    WARNING No matching plugin Grazie Lite version for product build 243.23654.189
    INFO Found matching plugin Kubernetes Runtime Configuration version 1.4.1
    INFO Found matching plugin Shell Script version 243.22562.53
    INFO Found matching plugin YAML version 243.23654.189
    INFO Found matching plugin Indent Rainbow version 2.2.0
    INFO Found matching plugin Grazie Pro version 0.3.359
    INFO Found matching plugin Unicorn Progress Bar version 1.1.4
    INFO Generating metadata for product IIC
    INFO Processing IIU
    INFO Product IIU is "IntelliJ IDEA Ultimate", and version 2024.3.2.2 is build 243.23654.189
    INFO Valid ideaIU-2024.3.2.2.tar.gz found on disk
    INFO Found matching plugin JavaDoc version 4.1.3
    INFO Found matching plugin File Watchers version 243.23654.19
    INFO Found matching plugin Zero Width Characters locator version 0.95
    WARNING No matching plugin Markdown version for product build 243.23654.189
    INFO Found matching plugin Terraform and HCL version 243.23654.44
    INFO Found matching plugin YouTrack Integration version 2024.2.123
    INFO Found matching plugin PowerShell version 2.8.0
    INFO Found matching plugin Go Template version 243.21565.122
    INFO Found matching plugin Unit File Support (systemd) version 242.250115.172
    WARNING No matching plugin Grazie Lite version for product build 243.23654.189
    INFO Found matching plugin Kubernetes Runtime Configuration version 1.4.1
    INFO Found matching plugin Shell Script version 243.22562.53
    INFO Found matching plugin YAML version 243.23654.189
    INFO Found matching plugin Indent Rainbow version 2.2.0
    INFO Found matching plugin Grazie Pro version 0.3.359
    INFO Found matching plugin Unicorn Progress Bar version 1.1.4
    INFO Generating metadata for product IIU
    INFO Processing PCP
    INFO Product PCP is "PyCharm Professional Edition", and version 2024.3.2 is build 243.23654.177
    INFO Valid pycharm-professional-2024.3.2.tar.gz found on disk
    INFO Found matching plugin JavaDoc version 4.1.3
    INFO Found matching plugin File Watchers version 243.23654.19
    INFO Found matching plugin Zero Width Characters locator version 0.95
    WARNING No matching plugin Markdown version for product build 243.23654.177
    INFO Found matching plugin Terraform and HCL version 243.23654.44
    INFO Found matching plugin YouTrack Integration version 2024.2.123
    INFO Found matching plugin PowerShell version 2.8.0
    INFO Found matching plugin Go Template version 243.21565.122
    INFO Found matching plugin Unit File Support (systemd) version 242.250115.172
    WARNING No matching plugin Grazie Lite version for product build 243.23654.177
    INFO Found matching plugin Kubernetes Runtime Configuration version 1.4.1
    INFO Found matching plugin Shell Script version 243.22562.53
    INFO Found matching plugin YAML version 243.23654.189
    INFO Found matching plugin Indent Rainbow version 2.2.0
    INFO Found matching plugin Grazie Pro version 0.3.359
    INFO Found matching plugin Unicorn Progress Bar version 1.1.4
    INFO Generating metadata for product PCP
    INFO Processing PS
    INFO Product PS is "PhpStorm", and version 2024.3.2.1 is build 243.23654.168
    INFO Found matching plugin JavaDoc version 4.1.3
    INFO Found matching plugin File Watchers version 243.23654.19
    INFO Found matching plugin Zero Width Characters locator version 0.95
    WARNING No matching plugin Markdown version for product build 243.23654.168
    INFO Found matching plugin Terraform and HCL version 243.23654.44
    INFO Found matching plugin YouTrack Integration version 2024.2.123
    INFO Found matching plugin PowerShell version 2.8.0
    INFO Found matching plugin Go Template version 243.21565.122
    INFO Found matching plugin Unit File Support (systemd) version 242.250115.172
    WARNING No matching plugin Grazie Lite version for product build 243.23654.168
    INFO Found matching plugin Kubernetes Runtime Configuration version 1.4.1
    INFO Found matching plugin Shell Script version 243.22562.53
    INFO Found matching plugin YAML version 243.23654.189
    INFO Found matching plugin Indent Rainbow version 2.2.0
    INFO Found matching plugin Grazie Pro version 0.3.359
    INFO Found matching plugin Unicorn Progress Bar version 1.1.4
    INFO Generating metadata for product PS
    INFO Processing RR
    INFO Product RR is "RustRover", and version 2024.3.4 is build 243.23654.180
    INFO Valid RustRover-2024.3.4.tar.gz found on disk
    INFO Found matching plugin JavaDoc version 4.1.3
    INFO Found matching plugin File Watchers version 243.23654.19
    INFO Found matching plugin Zero Width Characters locator version 0.95
    WARNING No matching plugin Markdown version for product build 243.23654.180
    INFO Found matching plugin Terraform and HCL version 243.23654.44
    INFO Found matching plugin YouTrack Integration version 2024.2.123
    INFO Found matching plugin PowerShell version 2.8.0
    INFO Found matching plugin Go Template version 243.21565.122
    INFO Found matching plugin Unit File Support (systemd) version 242.250115.172
    WARNING No matching plugin Grazie Lite version for product build 243.23654.180
    INFO Found matching plugin Kubernetes Runtime Configuration version 1.4.1
    INFO Found matching plugin Shell Script version 243.22562.53
    INFO Found matching plugin YAML version 243.23654.189
    INFO Found matching plugin Indent Rainbow version 2.2.0
    INFO Found matching plugin Grazie Pro version 0.3.359
    INFO Found matching plugin Unicorn Progress Bar version 1.1.4
    INFO Generating metadata for product RR
    INFO Found 88 files linked to the configuration
    WARNING Found 2 unknown files or directories in artefacts
    WARNING List of unknown items has been saved in `unknown.txt` for information
    WARNING To remove the unknown items, restart with --clean-unknown
    INFO Management of known/unknown files complete.
    INFO JetBrains product and plugins downloader finished.
