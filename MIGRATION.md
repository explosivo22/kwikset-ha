# Migration Guide: v0.3.x to v0.4.0

This guide provides step-by-step instructions for upgrading from Kwikset Smart Locks integration version 0.3.x to 0.4.0.

## ⚠️ Breaking Change: Folder Rename

**Version 0.4.0 introduces a breaking change** that requires manual intervention when upgrading.

The integration folder has been renamed from `kwikset-ha` to `kwikset` to align with Home Assistant's domain naming conventions. This change ensures the folder name matches the integration domain, which is required for proper Home Assistant functionality and future core integration compatibility.

### Why This Change?

Home Assistant requires that custom component folder names match their `domain` in `manifest.json`. The integration's domain has always been `kwikset`, but the folder was incorrectly named `kwikset-ha`. This mismatch has been corrected in v0.4.0.

| Version | Folder Name | Domain |
|---------|-------------|--------|
| 0.3.x | `custom_components/kwikset-ha/` | `kwikset` |
| 0.4.0+ | `custom_components/kwikset/` | `kwikset` |

---

## 🚨 Important: Read Before Upgrading

Because of the folder name change:

- **HACS cannot automatically upgrade** from v0.3.x to v0.4.0
- **Manual steps are required** to complete the upgrade
- **Your existing configuration will be preserved** (the domain hasn't changed)
- **Automations and dashboards will continue to work** after the upgrade

---

## 📋 Migration Options

Choose one of the following migration paths:

### Option A: Clean Installation (Recommended)

This is the safest and most straightforward method.

#### Step 1: Remove the Old Integration

1. Go to **Settings** → **Devices & Services**
2. Find **Kwikset Smart Locks**
3. Click the three-dot menu (⋮)
4. Select **Delete**
5. Confirm the removal

#### Step 2: Uninstall via HACS

1. Open **HACS** → **Integrations**
2. Find **Kwikset Smart Locks**
3. Click the three-dot menu (⋮)
4. Select **Remove** → **Remove**

#### Step 3: Delete the Old Folder

1. Access your Home Assistant configuration directory:
   - **Home Assistant OS/Supervised**: Use the File Editor add-on or SSH
   - **Container/Core**: Navigate to your config directory

2. Delete the old folder:
   ```bash
   rm -rf custom_components/kwikset-ha
   ```

   Or using File Editor:
   - Navigate to `custom_components/`
   - Delete the `kwikset-ha` folder

#### Step 4: Restart Home Assistant

1. Go to **Settings** → **System** → **Restart**
2. Wait for Home Assistant to fully restart

#### Step 5: Install the New Version

1. Open **HACS** → **Integrations**
2. Click the three-dot menu (⋮) in the top right
3. Select **Custom repositories**
4. Add: `https://github.com/explosivo22/kwikset-ha`
5. Category: **Integration**
6. Click **ADD**
7. Find **Kwikset Smart Locks** and click **Download**
8. Select version **0.4.0** or later
9. Click **Download**

#### Step 6: Restart Home Assistant Again

1. Go to **Settings** → **System** → **Restart**
2. Wait for Home Assistant to fully restart

#### Step 7: Re-add the Integration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **Kwikset Smart Locks**
4. Follow the setup wizard (enter credentials, MFA if required, select home)

---

### Option B: In-Place Migration

This method preserves your configuration but requires careful folder management.

#### Step 1: Back Up Your Configuration

1. Create a full Home Assistant backup:
   - Go to **Settings** → **System** → **Backups**
   - Click **Create Backup**
   - Wait for completion

2. Optionally, note your Kwikset configuration:
   - Go to **Settings** → **Devices & Services** → **Kwikset**
   - Note the polling interval setting if you changed it from the default

#### Step 2: Delete the Old Folder

1. Access your Home Assistant configuration directory
2. Delete the old integration folder:
   ```bash
   rm -rf custom_components/kwikset-ha
   ```

#### Step 3: Remove from HACS (Skip Download)

1. Open **HACS** → **Integrations**
2. Find **Kwikset Smart Locks** (may show as "Missing" or unavailable)
3. Click the three-dot menu (⋮)
4. Select **Remove** → **Remove**

#### Step 4: Re-add to HACS

1. Click the three-dot menu (⋮) in the top right
2. Select **Custom repositories**
3. Add: `https://github.com/explosivo22/kwikset-ha`
4. Category: **Integration**
5. Click **ADD**

#### Step 5: Download New Version

1. Find **Kwikset Smart Locks** and click **Download**
2. Select version **0.4.0** or later
3. Click **Download**

#### Step 6: Restart Home Assistant

1. Go to **Settings** → **System** → **Restart**
2. Wait for Home Assistant to fully restart

#### Step 7: Verify

1. Go to **Settings** → **Devices & Services**
2. Verify **Kwikset Smart Locks** is working
3. Check that your locks appear and are controllable

---

### Option C: Manual Installation

For users who installed manually without HACS.

#### Step 1: Back Up Your Configuration

Create a full Home Assistant backup before proceeding.

#### Step 2: Delete the Old Folder

```bash
rm -rf /config/custom_components/kwikset-ha
```

#### Step 3: Download the New Version

1. Go to [GitHub Releases](https://github.com/explosivo22/kwikset-ha/releases)
2. Download the latest release (v0.4.0 or later)
3. Extract the archive

#### Step 4: Install the New Folder

Copy the `kwikset` folder to your `custom_components` directory:

```bash
# Your structure should look like:
config/
└── custom_components/
    └── kwikset/           # New folder name
        ├── __init__.py
        ├── config_flow.py
        ├── const.py
        ├── manifest.json
        └── ...
```

#### Step 5: Restart Home Assistant

1. Go to **Settings** → **System** → **Restart**
2. Wait for Home Assistant to fully restart

#### Step 6: Verify

1. Go to **Settings** → **Devices & Services**
2. Verify **Kwikset Smart Locks** is working

---

## 🔧 Troubleshooting Migration Issues

### Both Folders Exist

If you see both `kwikset-ha` and `kwikset` folders:

1. Stop Home Assistant (if running)
2. Delete the old folder:
   ```bash
   rm -rf custom_components/kwikset-ha
   ```
3. Restart Home Assistant

### "Integration Not Found" Error

If Home Assistant can't find the integration after migration:

1. Verify the folder is correctly named `kwikset` (not `kwikset-ha`)
2. Verify all files are present in the folder
3. Check Home Assistant logs for errors:
   - Go to **Settings** → **System** → **Logs**
   - Look for entries containing "kwikset"
4. Restart Home Assistant

### HACS Shows Wrong Version

If HACS shows the old version or says the integration is missing:

1. Remove the repository from HACS custom repositories
2. Re-add it as a custom repository
3. Download the new version

### Configuration Lost

If your Kwikset configuration doesn't appear after migration:

1. The domain hasn't changed, so configuration should be preserved
2. If not, re-add the integration:
   - Go to **Settings** → **Devices & Services**
   - Click **+ Add Integration**
   - Search for **Kwikset Smart Locks**
   - Complete the setup wizard

### Entities Missing or Unavailable

After migration, if entities are unavailable:

1. Wait 1-2 minutes for the integration to poll the API
2. Check that your internet connection is working
3. Verify your Kwikset account credentials are still valid
4. Check the integration logs for errors

---

## 📊 What's Preserved After Migration

| Item | Preserved? | Notes |
|------|------------|-------|
| Entity IDs | ✅ Yes | Entity IDs use the domain `kwikset`, which hasn't changed |
| Device Registry | ✅ Yes | Devices are identified by their Kwikset ID |
| Automations | ✅ Yes | Automations using `lock.kwikset_*` entities will continue to work |
| Dashboard Cards | ✅ Yes | Dashboard configurations are unaffected |
| Configuration Options | ⚠️ Depends | Using Option A (Clean Install) requires reconfiguring options |
| Credentials | ⚠️ Depends | Using Option A (Clean Install) requires re-entering credentials |

---

## ❓ Frequently Asked Questions

### Q: Why was this change necessary?

**A:** Home Assistant requires that custom component folder names match their domain. Having `kwikset-ha` as the folder name but `kwikset` as the domain was non-standard and could cause issues with future Home Assistant updates.

### Q: Will my automations break?

**A:** No. Your automations reference entity IDs like `lock.front_door_lock`, which are based on the domain (`kwikset`) not the folder name. Since the domain hasn't changed, your automations will continue to work.

### Q: Can I skip this migration?

**A:** You can continue using v0.3.x, but you won't receive updates, bug fixes, or new features. It's recommended to migrate to stay current.

### Q: What if I have issues after migrating?

**A:** 
1. Check the troubleshooting section above
2. Review Home Assistant logs
3. Open an issue on [GitHub](https://github.com/explosivo22/kwikset-ha/issues) with your logs

### Q: Do I need to re-pair my locks?

**A:** No. Your locks remain registered with your Kwikset account. You only need to re-authenticate with the integration if you used Option A (Clean Install).

---

## 📞 Getting Help

If you encounter issues during migration:

1. **GitHub Issues**: [Open an issue](https://github.com/explosivo22/kwikset-ha/issues)
2. **GitHub Discussions**: [Start a discussion](https://github.com/explosivo22/kwikset-ha/discussions)
3. **Home Assistant Community**: [Forum](https://community.home-assistant.io/)

When reporting issues, please include:
- Your Home Assistant version
- The migration option you attempted
- Any error messages from the logs
- The contents of your `custom_components/` directory

---

## 📝 Version History

| Version | Folder Name | Notes |
|---------|-------------|-------|
| 0.1.x - 0.3.5 | `kwikset-ha` | Original folder name |
| 0.4.0+ | `kwikset` | Corrected to match domain |

---

*Last updated: December 2025*
