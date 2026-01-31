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
