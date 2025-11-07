# Quick Start: Dynamic Device Discovery

## What's New?

Your Kwikset integration now automatically discovers new devices! No need to reconfigure when you add new locks.

## How It Works

### Automatic (Default)
- Every 5 minutes, the integration checks for new devices
- New locks appear automatically in Home Assistant
- Removed locks disappear automatically

### Manual (When You Want It Now)

#### Method 1: Options Menu
1. Go to **Settings** → **Devices & Services**
2. Find **Kwikset Smart Locks**
3. Click **Configure**
4. Check **"Reload integration to discover new devices"**
5. Click **Submit**
6. ✅ New devices appear!

#### Method 2: Reconfigure
1. Go to **Settings** → **Devices & Services**
2. Find **Kwikset Smart Locks**
3. Click the **⋮** (three dots) menu
4. Select **Reconfigure**
5. Click **Submit**
6. ✅ New devices appear!

## Common Questions

### Q: I just added a new lock. How long until it appears?
**A:** Within 5 minutes automatically, or instantly using manual methods above.

### Q: Will my existing locks stop working?
**A:** No! This is a non-breaking change. Everything continues to work.

### Q: What happens when I remove a lock from my Kwikset account?
**A:** It will be removed from Home Assistant automatically within 5 minutes.

### Q: Can I change how often it checks for new devices?
**A:** Currently it's every 5 minutes. Future versions may allow customization.

### Q: Do I need to do anything after updating?
**A:** No! Device discovery starts automatically after the update.

## Troubleshooting

### New device not appearing?
1. Verify the device is in your Kwikset app
2. Wait up to 5 minutes for automatic discovery
3. Try manual discovery using options menu
4. Check Home Assistant logs for errors

### Removed device still showing?
1. Wait up to 5 minutes for automatic cleanup
2. Try manual discovery/reconfigure
3. Manually remove from Devices page if needed

### Integration won't reload?
1. Check Home Assistant logs
2. Verify your Kwikset credentials are valid
3. Try reauthentication if prompted

## Support

For issues or questions:
- Check Home Assistant logs: **Settings** → **System** → **Logs**
- Report issues on GitHub: [kwikset-ha repository](https://github.com/explosivo22/kwikset-ha/)

## Technical Details

Want to understand how it works? See:
- `DYNAMIC_DEVICE_DISCOVERY.md` - Technical documentation
- `IMPLEMENTATION_SUMMARY.md` - Code changes summary
