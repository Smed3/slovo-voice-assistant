import { TrayIcon, TrayIconEvent } from '@tauri-apps/api/tray';
import { Menu, MenuItem, PredefinedMenuItem } from '@tauri-apps/api/menu';
import { getCurrentWindow } from '@tauri-apps/api/window';
import { exit } from '@tauri-apps/plugin-process';

let trayIcon: TrayIcon | null = null;

/**
 * Initialize the system tray icon and menu
 */
export async function initializeTray(): Promise<void> {
  // Create tray menu items
  const showItem = await MenuItem.new({
    id: 'show',
    text: 'Show Slovo',
    action: async () => {
      const window = getCurrentWindow();
      await window.show();
      await window.setFocus();
    },
  });

  const hideItem = await MenuItem.new({
    id: 'hide',
    text: 'Hide',
    action: async () => {
      const window = getCurrentWindow();
      await window.hide();
    },
  });

  const separator = await PredefinedMenuItem.new({ item: 'Separator' });

  const settingsItem = await MenuItem.new({
    id: 'settings',
    text: 'Settings',
    action: async () => {
      // TODO: Open settings window
      console.log('Settings clicked');
    },
  });

  const separator2 = await PredefinedMenuItem.new({ item: 'Separator' });

  const quitItem = await MenuItem.new({
    id: 'quit',
    text: 'Quit Slovo',
    action: async () => {
      await exit(0);
    },
  });

  // Create the menu
  const menu = await Menu.new({
    items: [showItem, hideItem, separator, settingsItem, separator2, quitItem],
  });

  // Create the tray icon
  trayIcon = await TrayIcon.new({
    id: 'slovo-tray',
    tooltip: 'Slovo Voice Assistant',
    menu,
    menuOnLeftClick: false,
    action: async (event: TrayIconEvent) => {
      // Handle left click - toggle window visibility
      if (event.type === 'Click' && event.button === 'Left') {
        const window = getCurrentWindow();
        const isVisible = await window.isVisible();
        if (isVisible) {
          await window.hide();
        } else {
          await window.show();
          await window.setFocus();
        }
      }
    },
  });

  console.log('System tray initialized');
}

/**
 * Update the tray icon tooltip
 */
export async function updateTrayTooltip(tooltip: string): Promise<void> {
  if (trayIcon) {
    await trayIcon.setTooltip(tooltip);
  }
}

/**
 * Destroy the tray icon
 */
export async function destroyTray(): Promise<void> {
  if (trayIcon) {
    // Tray cleanup is handled automatically by Tauri
    trayIcon = null;
  }
}
