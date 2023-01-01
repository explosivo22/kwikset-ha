# Kwikset Smart Locks for Home Assistant

Support for [Kwikset Smart Locks](https://www.kwikset.com/products/electronic/electronic-smart-locks) for Home Assistant.

[![License](https://img.shields.io/github/license/explosivo22/rinnaicontrolr-ha?style=for-the-badge)](https://opensource.org/licenses/Apache-2.0)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

<a href="https://www.buymeacoffee.com/Explosivo22" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-blue.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

## WARNING

* **THIS LIBRARY ONLY WORKS IF YOU HAVE CREATED A HOME OR HAVE BEEN INVITED TO A HOME FROM THE KWIKSET APP**
* [IOS/Android](https://www.kwikset.com/smart-locks/app)

## IMPORTANT NOTES

* **KWIKSET DOESN'T PROVIDE ANY OFFICIALLY SUPPORTED API, THUS THEIR CHANGES MAY BREAK HASS INTEGRATIONS AT ANY TIME.**

### Features

- lock:
    * lock/unlock device
- multiple Kwikset Homes

## Installation

#### Versions

The 'main' branch of this custom component is considered unstable, alpha quality and not guaranteed to work.
Please make sure to use one of the official release branches when installing using HACS, see [what has changed in each version](https://github.com/explosivo22/kwikset-ha/releases).

### Step 1: Install Custom Components

1) Go to integrations in HACS
2) click the 3 dots in the top right corner and choose `custom repositories`
3) paste the following into the repository input field `https://github.com/explosivo22/kwikset-ha`  and choose category of `Integration`
4) click add and restart HA to let the integration load
5) Recommended to clear the cache and reload first before adding the integration.
6) Go to settings and choose integrations.
7) Click `Add Integration` and search for `Kwikset Smart Locks`
8) Configure the integration.