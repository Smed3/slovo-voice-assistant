//! Error types for Slovo

use thiserror::Error;

#[derive(Error, Debug)]
pub enum SlovoError {
    #[error("Failed to connect to agent: {0}")]
    AgentConnection(String),

    #[error("Agent error: {0}")]
    AgentError(String),

    #[error("Voice processing error: {0}")]
    VoiceError(String),

    #[error("Configuration error: {0}")]
    ConfigError(String),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),
}

impl std::fmt::Display for SlovoError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SlovoError::AgentConnection(msg) => write!(f, "Agent connection error: {}", msg),
            SlovoError::AgentError(msg) => write!(f, "Agent error: {}", msg),
            SlovoError::VoiceError(msg) => write!(f, "Voice processing error: {}", msg),
            SlovoError::ConfigError(msg) => write!(f, "Configuration error: {}", msg),
            SlovoError::IoError(e) => write!(f, "IO error: {}", e),
        }
    }
}
