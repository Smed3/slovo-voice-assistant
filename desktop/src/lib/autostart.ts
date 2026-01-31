import { enable, isEnabled, disable } from '@tauri-apps/plugin-autostart';

/**
 * Initialize autostart configuration
 * Enables the app to start automatically on Windows boot
 */
export async function initializeAutostart(): Promise<void> {
  try {
    const enabled = await isEnabled();
    
    if (!enabled) {
      // Enable autostart by default for first run
      await enable();
      console.log('Autostart enabled');
    } else {
      console.log('Autostart already enabled');
    }
  } catch (error) {
    console.error('Failed to configure autostart:', error);
  }
}

/**
 * Check if autostart is currently enabled
 */
export async function getAutostartStatus(): Promise<boolean> {
  try {
    return await isEnabled();
  } catch (error) {
    console.error('Failed to check autostart status:', error);
    return false;
  }
}

/**
 * Enable autostart
 */
export async function enableAutostart(): Promise<void> {
  try {
    await enable();
    console.log('Autostart enabled');
  } catch (error) {
    console.error('Failed to enable autostart:', error);
    throw error;
  }
}

/**
 * Disable autostart
 */
export async function disableAutostart(): Promise<void> {
  try {
    await disable();
    console.log('Autostart disabled');
  } catch (error) {
    console.error('Failed to disable autostart:', error);
    throw error;
  }
}
