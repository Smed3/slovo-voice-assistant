#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod agent;
mod commands;
mod error;
mod tray;

use tauri::Manager;
use tracing::info;
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt};

fn main() {
    // Initialize logging
    tracing_subscriber::registry()
        .with(tracing_subscriber::EnvFilter::new(
            std::env::var("RUST_LOG").unwrap_or_else(|_| "info".into()),
        ))
        .with(tracing_subscriber::fmt::layer())
        .init();

    info!("Starting Slovo Voice Assistant");

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_autostart::init(
            tauri_plugin_autostart::MacosLauncher::LaunchAgent,
            Some(vec!["--autostart"]),
        ))
        .plugin(tauri_plugin_process::init())
        .setup(|app| {
            let handle = app.handle().clone();
            
            // Check if launched with autostart flag
            let args: Vec<String> = std::env::args().collect();
            let is_autostart = args.contains(&"--autostart".to_string());
            
            info!("Autostart mode: {}", is_autostart);

            // Get the main window
            if let Some(window) = app.get_webview_window("main") {
                if is_autostart {
                    // Hide window on autostart, keep in tray
                    info!("Started in background mode");
                    // Window is already hidden by default in config
                } else {
                    // Show window for normal launch
                    let _ = window.show();
                    let _ = window.set_focus();
                }

                // Handle window close - minimize to tray instead
                let window_clone = window.clone();
                window.on_window_event(move |event| {
                    if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                        // Prevent actual close, hide to tray instead
                        api.prevent_close();
                        let _ = window_clone.hide();
                        info!("Window hidden to tray");
                    }
                });
            }

            // Spawn agent health check task
            let handle_clone = handle.clone();
            tauri::async_runtime::spawn(async move {
                agent::monitor_agent_health(handle_clone).await;
            });

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            commands::process_voice_input,
            commands::check_agent_status,
            commands::send_message_to_agent,
            commands::show_window,
            commands::hide_window,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
