//! Tauri commands for frontend-backend communication

use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Manager};
use tracing::{error, info};

use crate::agent::AgentClient;
use crate::error::SlovoError;

/// Response type for command results
#[derive(Debug, Serialize)]
pub struct CommandResponse<T> {
    pub success: bool,
    pub data: Option<T>,
    pub error: Option<String>,
}

impl<T> CommandResponse<T> {
    pub fn ok(data: T) -> Self {
        Self {
            success: true,
            data: Some(data),
            error: None,
        }
    }

    pub fn err(error: impl ToString) -> Self {
        Self {
            success: false,
            data: None,
            error: Some(error.to_string()),
        }
    }
}

/// Agent status response
#[derive(Debug, Serialize)]
pub struct AgentStatusResponse {
    pub status: String,
    pub version: Option<String>,
}

/// Chat message response
#[derive(Debug, Serialize)]
pub struct ChatMessageResponse {
    pub id: String,
    pub response: String,
    pub conversation_id: String,
    pub reasoning: Option<String>,
}

/// Process voice input audio data
#[tauri::command]
pub async fn process_voice_input(audio_data: Vec<u8>) -> Result<String, String> {
    info!("Processing voice input: {} bytes", audio_data.len());
    
    // TODO: Implement actual voice processing
    // This would:
    // 1. Send audio to STT service
    // 2. Return transcribed text
    
    // For now, return a placeholder
    Ok("Voice input processing not yet implemented".to_string())
}

/// Check the agent runtime status
#[tauri::command]
pub async fn check_agent_status() -> CommandResponse<AgentStatusResponse> {
    let client = AgentClient::new();
    
    match client.health_check().await {
        Ok(health) => CommandResponse::ok(AgentStatusResponse {
            status: health.status,
            version: Some(health.version),
        }),
        Err(e) => {
            error!("Agent status check failed: {}", e);
            CommandResponse::ok(AgentStatusResponse {
                status: "disconnected".to_string(),
                version: None,
            })
        }
    }
}

/// Send a message to the agent and get a response
#[tauri::command]
pub async fn send_message_to_agent(
    message: String,
    conversation_id: Option<String>,
) -> CommandResponse<ChatMessageResponse> {
    info!("Sending message to agent: {}", message);
    
    let client = AgentClient::new();
    
    match client.send_message(&message, conversation_id.as_deref()).await {
        Ok(response) => {
            info!("Received response from agent");
            CommandResponse::ok(ChatMessageResponse {
                id: response.id,
                response: response.response,
                conversation_id: response.conversation_id,
                reasoning: response.reasoning,
            })
        }
        Err(e) => {
            error!("Failed to send message to agent: {}", e);
            CommandResponse::err(e)
        }
    }
}

/// Show the main window
#[tauri::command]
pub async fn show_window(app: AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window.show().map_err(|e| e.to_string())?;
        window.set_focus().map_err(|e| e.to_string())?;
        info!("Window shown");
        Ok(())
    } else {
        Err("Main window not found".to_string())
    }
}

/// Hide the main window to tray
#[tauri::command]
pub async fn hide_window(app: AppHandle) -> Result<(), String> {
    if let Some(window) = app.get_webview_window("main") {
        window.hide().map_err(|e| e.to_string())?;
        info!("Window hidden");
        Ok(())
    } else {
        Err("Main window not found".to_string())
    }
}
