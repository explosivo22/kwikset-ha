# Kwikset Smart Locks for Home Assistant

Support for [Kwikset Smart Locks](https://www.kwikset.com/products/electronic/electronic-smart-locks) for Home Assistant.

[![License](https://img.shields.io/github/license/explosivo22/rinnaicontrolr-ha?style=for-the-badge)](https://opensource.org/licenses/Apache-2.0)
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge)](https://github.com/custom-components/hacs)

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

Make sure that [Home Assistant Community Store (HACS)](https://github.com/custom-components/hacs) is setup, then add the "Integration" custom repository: `explosivo22/kwikset-ha`.

### Step 2: Configuration

#### Configure via UI

Go to Configuration -> Integrations and click the + symbol to configure. Search for Kwikset Smart Locks and follow the prompts.