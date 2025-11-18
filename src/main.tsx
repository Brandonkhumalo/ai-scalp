import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";

const rootElement = document.getElementById("root");

if (!rootElement) {
  throw new Error("Failed to find the root element. Please check your HTML file.");
}

try {
  console.log("ZimAI Trader - Initializing application...");
  
  createRoot(rootElement).render(<App />);
  
  console.log("ZimAI Trader - Application successfully mounted");
} catch (error) {
  console.error("CRITICAL ERROR: Failed to initialize application:", error);
  
  rootElement.innerHTML = `
    <div style="
      min-height: 100vh;
      background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 20px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    ">
      <div style="
        max-width: 600px;
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 40px;
        text-align: center;
      ">
        <div style="
          width: 64px;
          height: 64px;
          background: rgba(239, 68, 68, 0.2);
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          margin: 0 auto 24px;
        ">
          <svg width="32" height="32" fill="none" stroke="#f87171" stroke-width="2" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/>
          </svg>
        </div>
        <h1 style="color: white; font-size: 24px; font-weight: bold; margin-bottom: 16px;">
          Application Error
        </h1>
        <p style="color: #9ca3af; margin-bottom: 24px;">
          ZimAI Trader failed to initialize. This may be due to a browser compatibility issue or corrupted cache.
        </p>
        <button onclick="
          if (confirm('Clear application cache and reload?')) {
            localStorage.clear();
            sessionStorage.clear();
            window.location.reload();
          }
        " style="
          background: #3b82f6;
          color: white;
          border: none;
          padding: 12px 24px;
          border-radius: 8px;
          font-size: 16px;
          font-weight: 500;
          cursor: pointer;
          margin-right: 8px;
        ">
          Clear Cache & Reload
        </button>
        <button onclick="window.location.href='mailto:support@zimai.trader'" style="
          background: transparent;
          color: white;
          border: 1px solid rgba(255, 255, 255, 0.2);
          padding: 12px 24px;
          border-radius: 8px;
          font-size: 16px;
          font-weight: 500;
          cursor: pointer;
        ">
          Contact Support
        </button>
        <details style="margin-top: 24px; text-align: left;">
          <summary style="color: #9ca3af; cursor: pointer; font-size: 14px;">
            Technical Details
          </summary>
          <pre style="
            color: #f87171;
            font-size: 12px;
            margin-top: 8px;
            padding: 12px;
            background: rgba(0, 0, 0, 0.3);
            border-radius: 8px;
            overflow-x: auto;
          ">${error instanceof Error ? error.message : String(error)}</pre>
        </details>
      </div>
    </div>
  `;
}
