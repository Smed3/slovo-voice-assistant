//! System tray management module
//! 
//! Note: Most tray functionality is now handled via the frontend using @tauri-apps/api/tray
//! This module contains any native tray utilities if needed.

use tracing::info;

/// Tray icon states
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum TrayState {
    /// Normal idle state
    Idle,
    /// Listening for voice input
    Listening,
    /// Processing request
    Processing,
    /// Error state
    Error,
}

impl TrayState {
    /// Get the icon filename for this state
    pub fn icon_name(&self) -> &'static str {
        match self {
            TrayState::Idle => "icon.png",
            TrayState::Listening => "icon-listening.png",
            TrayState::Processing => "icon-processing.png",
            TrayState::Error => "icon-error.png",
        }
    }

    /// Get the tooltip text for this state
    pub fn tooltip(&self) -> &'static str {
        match self {
            TrayState::Idle => "Slovo Voice Assistant",
            TrayState::Listening => "Slovo - Listening...",
            TrayState::Processing => "Slovo - Processing...",
            TrayState::Error => "Slovo - Error",
        }
    }
}

/// Initialize tray state tracking
pub fn init_tray() {
    info!("Tray state tracking initialized");
}
