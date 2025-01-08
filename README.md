# Kwikset Smart Locks for Home Assistant

Support for [Kwikset Smart Locks](https://www.kwikset.com/products/electronic/electronic-smart-locks) for Home Assistant.

[![License](https://img.shields.io/github/license/explosivo22/rinnaicontrolr-ha?style=for-the-badge)](https://opensource.org/licenses/Apache-2.0)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)
[![HA integration usage](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json&query=%24.kwikset.total&style=for-the-badge&logo=home-assistant&label=integration%20usage&color=41BDF5)](https://analytics.home-assistant.io/custom_integrations.json)

<a href="https://www.buymeacoffee.com/Explosivo22" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-blue.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

## WARNING

* **THIS LIBRARY ONLY WORKS IF YOU HAVE CREATED A HOME OR HAVE BEEN INVITED TO A HOME FROM THE KWIKSET APP**
* [IOS/Android](https://www.kwikset.com/smart-locks/app)

## IMPORTANT NOTES

* **KWIKSET DOESN'T PROVIDE ANY OFFICIALLY SUPPORTED API, THUS THEIR CHANGES MAY BREAK HASS INTEGRATIONS AT ANY TIME.**
* **THIS INTEGRATION CURRENTLY REQUIRES 2-STEP VERIFICATION TO BE ENABLED.**

### Features

- lock:
    * lock/unlock device
- multiple Kwikset Homes

## Installation

#### Versions

The 'main' branch of this custom component is considered unstable, alpha quality and not guaranteed to work.
Please make sure to use one of the official release branches when installing using HACS, see [what has changed in each version](https://github.com/explosivo22/kwikset-ha/releases).

#### With HACS

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=explosivo22&repository=kwikset-ha&category=integration)

#### Manual
1. Copy the `kwikset` directory from `custom_components` in this repository and place inside your Home Assistant's `custom_components` directory.
2. Restart Home Assistant
3. Follow the instructions in the `Setup` section

> [!WARNING]
> If installing manually, in order to be alerted about new releases, you will need to subscribe to releases from this repository.

# Setup
[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=kwikset)

> [!Tip]
> If you are unable to use the button above, follow the steps below:
> 1. Navigate to the Home Assistant Integrations page `(Settings --> Devices & Services)`
> 2. Click the `+ ADD INTEGRATION` button in the lower right-hand corner
> 3. Search for `Kwikset Smart Locks`