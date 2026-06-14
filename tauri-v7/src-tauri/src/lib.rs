// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::Command;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let (python_cmd, script_path) = if cfg!(target_os = "windows") {
                let exe_dir = std::env::current_exe()
                    .unwrap_or_default()
                    .parent()
                    .unwrap_or(std::path::Path::new("."))
                    .to_path_buf();
                (exe_dir.join("pdf-label-backend.exe").to_string_lossy().to_string(), None)
            } else {
                // Resolve sidecar script relative to the project root
                let script = if std::path::PathBuf::from("sidecar/server.py").exists() {
                    std::path::PathBuf::from("sidecar/server.py")
                } else if std::path::PathBuf::from("../sidecar/server.py").exists() {
                    std::path::PathBuf::from("../sidecar/server.py")
                } else {
                    // Try relative to exe
                    std::env::current_exe()
                        .unwrap_or_default()
                        .parent()
                        .unwrap_or(std::path::Path::new("."))
                        .join("../sidecar/server.py")
                        .to_path_buf()
                };
                ("/home/spark/pdf-label-env/bin/python3".to_string(), Some(script.to_string_lossy().to_string()))
            };

            let mut cmd = Command::new(&python_cmd);
            if let Some(ref path) = script_path {
                cmd.arg(path);
            }

            cmd.env("PDF_LABEL_PORT", "8502")
               .env("PDF_LABEL_HOST", "127.0.0.1");

            match cmd.spawn() {
                Ok(mut child) => {
                    println!("Python backend started (PID: {})", child.id());
                    // Hold child handle in a thread for cleanup
                    std::thread::spawn(move || {
                        let _ = child.wait();
                    });
                }
                Err(e) => {
                    eprintln!("Failed to start Python backend: {}", e);
                }
            }

            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
