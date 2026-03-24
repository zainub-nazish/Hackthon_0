module.exports = {
  apps: [
    {
      name: "filesystem-watcher",
      script: "D:\\Hackthon_0\\silver_tier_22\\watchers\\filesystem_watcher.py",
      interpreter: "D:\\Hackthon_0\\silver_tier_22\\.venv\\Scripts\\python.exe",
      restart_delay: 5000,
      max_restarts: 20,
      watch: false,
      autorestart: true,
    },
    {
      name: "gmail-watcher",
      script: "D:\\Hackthon_0\\silver_tier_22\\Scripts\\gmail_watcher.py",
      interpreter: "D:\\Hackthon_0\\silver_tier_22\\.venv\\Scripts\\python.exe",
      restart_delay: 10000,
      max_restarts: 20,
      watch: false,
      autorestart: true,
    },
    {
      name: "linkedin-watcher",
      script: "D:\\Hackthon_0\\silver_tier_22\\Scripts\\linkedin_watcher.py",
      interpreter: "D:\\Hackthon_0\\silver_tier_22\\.venv\\Scripts\\python.exe",
      restart_delay: 15000,
      max_restarts: 20,
      watch: false,
      autorestart: true,
    },
    {
      name: "whatsapp-watcher",
      script: "D:\\Hackthon_0\\silver_tier_22\\Scripts\\whatsapp_watcher.py",
      interpreter: "D:\\Hackthon_0\\silver_tier_22\\.venv\\Scripts\\python.exe",
      restart_delay: 15000,
      max_restarts: 20,
      watch: false,
      autorestart: true,
    },
    {
      name: "approval-watcher",
      script: "D:\\Hackthon_0\\silver_tier_22\\Scripts\\approval_watcher.py",
      interpreter: "D:\\Hackthon_0\\silver_tier_22\\.venv\\Scripts\\python.exe",
      restart_delay: 5000,
      max_restarts: 20,
      watch: false,
      autorestart: true,
      args: "--poll 30",
    },
    {
      name: "orchestrator-cron",
      script: "D:\\Hackthon_0\\silver_tier_22\\Scripts\\orchestrator.py",
      interpreter: "D:\\Hackthon_0\\silver_tier_22\\.venv\\Scripts\\python.exe",
      args: "--mode cron-only",
      watch: false,
      autorestart: true,
      max_restarts: 20,
    }
  ]
};
