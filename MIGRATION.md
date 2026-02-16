# Migration Guide: v0.3.x to v0.4.0

## ⚠️ Breaking Change: Folder Rename

The integration folder has been renamed from `kwikset-ha` to `kwikset` to match Home Assistant's domain naming conventions. HACS cannot automatically upgrade across this rename, so a clean reinstall is required.

| Version | Folder Name |
|---------|-------------|
| 0.3.x | `custom_components/kwikset-ha/` |
| 0.4.0+ | `custom_components/kwikset/` |

---

## Migration Steps (Required)

1. **Remove the integration from Home Assistant**
   Settings → Devices & Services → Kwikset → Delete

2. **Remove via HACS**
   HACS → Integrations → Kwikset → Remove
   *(This deletes the old `kwikset-ha` folder automatically)*

3. **Restart Home Assistant**

4. **Install v0.4.0+ fresh via HACS**
   [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=explosivo22&repository=kwikset-ha&category=integration)
   *(Select version 0.4.0 or later when prompted)*

5. **Re-add the integration**
   Settings → Devices & Services → Add Integration → Kwikset
   [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=kwikset)

6. **Update any automations** referencing old entity IDs (e.g., `lock.kwikset_ha_*` → `lock.kwikset_*`)

---

## Manual Installation (without HACS)

1. Delete the old folder: `rm -rf custom_components/kwikset-ha`
2. Download the latest release from [GitHub Releases](https://github.com/explosivo22/kwikset-ha/releases)
3. Copy the `kwikset` folder into `custom_components/`
4. Restart Home Assistant
5. Re-add the integration

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Both `kwikset-ha` and `kwikset` folders exist | Delete `custom_components/kwikset-ha` and restart |
| "Integration Not Found" error | Verify the folder is named `kwikset` (not `kwikset-ha`) and restart |
| HACS shows wrong version | Remove and re-add the custom repository in HACS |
| Entities missing or unavailable | Wait 1–2 minutes for API polling, then check logs |

---

## Getting Help

- [GitHub Issues](https://github.com/explosivo22/kwikset-ha/issues)
- [GitHub Discussions](https://github.com/explosivo22/kwikset-ha/discussions)
- [Home Assistant Community Forum](https://community.home-assistant.io/)
