//! Agent runtime IPC module
//! 
//! Handles communication between the Tauri desktop app and the Python agent runtime
//! via localhost HTTP.

use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::time::Duration;
use tauri::{AppHandle, Emitter};
use tracing::{error, info, warn};

use crate::error::SlovoError;

/// Agent runtime configuration
const AGENT_HOST: &str = "127.0.0.1";
const AGENT_PORT: u16 = 8741;
const HEALTH_CHECK_INTERVAL: Duration = Duration::from_secs(10);

/// Agent health status
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AgentHealth {
    pub status: String,
    pub version: String,
    pub uptime: f64,
}

/// Chat request to the agent
#[derive(Debug, Serialize)]
pub struct ChatRequest {
    pub message: String,
    pub conversation_id: Option<String>,
}

/// Chat response from the agent
#[derive(Debug, Deserialize)]
pub struct ChatResponse {
    pub id: String,
    pub response: String,
    pub conversation_id: String,
    pub reasoning: Option<String>,
}

/// Agent client for IPC communication
#[derive(Clone)]
pub struct AgentClient {
    client: Client,
    base_url: String,
}

impl AgentClient {
    /// Create a new agent client
    pub fn new() -> Self {
        let client = Client::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .expect("Failed to create HTTP client");

        Self {
            client,
            base_url: format!("http://{}:{}", AGENT_HOST, AGENT_PORT),
        }
    }

    /// Check agent health
    pub async fn health_check(&self) -> Result<AgentHealth, SlovoError> {
        let url = format!("{}/health", self.base_url);
        
        let response = self
            .client
            .get(&url)
            .send()
            .await
            .map_err(|e| SlovoError::AgentConnection(e.to_string()))?;

        if !response.status().is_success() {
            return Err(SlovoError::AgentConnection(format!(
                "Health check failed with status: {}",
                response.status()
            )));
        }

        response
            .json::<AgentHealth>()
            .await
            .map_err(|e| SlovoError::AgentConnection(e.to_string()))
    }

    /// Send a chat message to the agent
    pub async fn send_message(&self, message: &str, conversation_id: Option<&str>) -> Result<ChatResponse, SlovoError> {
        let url = format!("{}/api/v1/chat", self.base_url);
        
        let request = ChatRequest {
            message: message.to_string(),
            conversation_id: conversation_id.map(|s| s.to_string()),
        };

        let response = self
            .client
            .post(&url)
            .json(&request)
            .send()
            .await
            .map_err(|e| SlovoError::AgentConnection(e.to_string()))?;

        if !response.status().is_success() {
            let status = response.status();
            let error_text = response.text().await.unwrap_or_default();
            return Err(SlovoError::AgentError(format!(
                "Chat request failed with status {}: {}",
                status, error_text
            )));
        }

        response
            .json::<ChatResponse>()
            .await
            .map_err(|e| SlovoError::AgentConnection(e.to_string()))
    }
}

impl Default for AgentClient {
    fn default() -> Self {
        Self::new()
    }
}

/// Monitor agent health and emit status updates
pub async fn monitor_agent_health(app: AppHandle) {
    let client = AgentClient::new();
    let mut last_status = "disconnected".to_string();

    loop {
        let status = match client.health_check().await {
            Ok(health) => {
                if health.status == "healthy" {
                    "connected"
                } else {
                    "degraded"
                }
            }
            Err(e) => {
                if last_status != "disconnected" {
                    warn!("Agent health check failed: {}", e);
                }
                "disconnected"
            }
        };

        // Only emit if status changed
        if status != last_status {
            info!("Agent status changed: {} -> {}", last_status, status);
            let _ = app.emit("agent-status-changed", status);
            last_status = status.to_string();
        }

        tokio::time::sleep(HEALTH_CHECK_INTERVAL).await;
    }
}
