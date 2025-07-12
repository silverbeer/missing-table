#!/usr/bin/env python3
"""
Start both backend and frontend services for Missing Table application.
"""
import subprocess
import sys
import time
import os
import signal
from pathlib import Path

class ServiceManager:
    def __init__(self):
        self.processes = {}
        self.root_dir = Path(__file__).parent
        self.supabase_started = False
        
    def check_directories(self):
        """Check if backend and frontend directories exist."""
        if not (self.root_dir / "backend").exists():
            print("❌ Error: backend directory not found!")
            return False
        if not (self.root_dir / "frontend").exists():
            print("❌ Error: frontend directory not found!")
            return False
        return True
    
    def check_and_start_supabase(self):
        """Check if Supabase is running and start it if not."""
        print("🔍 Checking Supabase status...")
        backend_dir = self.root_dir / "backend"
        
        try:
            # Check if supabase is running
            result = subprocess.run(
                ["npx", "supabase", "status"],
                cwd=backend_dir,
                capture_output=True,
                text=True
            )
            
            if "supabase local development setup is running" in result.stdout:
                print("✅ Supabase is already running")
                self.supabase_started = False
            else:
                print("🚀 Starting Supabase...")
                subprocess.run(
                    ["npx", "supabase", "start"],
                    cwd=backend_dir,
                    check=True
                )
                self.supabase_started = True
                print("✅ Supabase started successfully")
                time.sleep(5)  # Give Supabase time to fully start
                
        except subprocess.CalledProcessError:
            print("⚠️  Failed to start Supabase. Make sure Docker is running.")
            raise
    
    def start_backend(self):
        """Start the backend service."""
        print("🚀 Starting backend server...")
        backend_dir = self.root_dir / "backend"
        
        # Check for uv
        try:
            subprocess.run(["uv", "--version"], capture_output=True, check=True)
            cmd = ["uv", "run", "python", "app.py"]
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠️  uv not found, using python directly")
            cmd = [sys.executable, "app.py"]
        
        # Load environment variables if .env.local exists
        env = os.environ.copy()
        env_file = backend_dir / ".env.local"
        if env_file.exists():
            print("📋 Loading .env.local configuration")
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        env[key] = value
        
        self.processes['backend'] = subprocess.Popen(
            cmd,
            cwd=backend_dir,
            env=env
        )
        
    def start_frontend(self):
        """Start the frontend service."""
        print("\n🚀 Starting frontend server...")
        frontend_dir = self.root_dir / "frontend"
        
        # Check if node_modules exists
        if not (frontend_dir / "node_modules").exists():
            print("📦 Installing frontend dependencies...")
            subprocess.run(["npm", "install"], cwd=frontend_dir, check=True)
        
        self.processes['frontend'] = subprocess.Popen(
            ["npm", "run", "serve"],
            cwd=frontend_dir
        )
    
    def cleanup(self, signum=None, frame=None):
        """Clean up all processes on exit."""
        print("\n\n⏹️  Shutting down services...")
        
        for name, process in self.processes.items():
            if process and process.poll() is None:
                print(f"   Stopping {name}...")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
        
        # Stop Supabase if we started it
        if self.supabase_started:
            print("   Stopping Supabase...")
            backend_dir = self.root_dir / "backend"
            subprocess.run(["npx", "supabase", "stop"], cwd=backend_dir)
        
        print("✅ All services stopped.")
        sys.exit(0)
    
    def run(self):
        """Run both services."""
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.cleanup)
        signal.signal(signal.SIGTERM, self.cleanup)
        
        print("🎯 Starting Missing Table application...\n")
        
        if not self.check_directories():
            sys.exit(1)
        
        try:
            # Check and start Supabase if needed
            self.check_and_start_supabase()
            
            # Start backend
            self.start_backend()
            
            # Wait for backend to initialize
            print("⏳ Waiting for backend to start...")
            time.sleep(3)
            
            # Check if backend is still running
            if self.processes['backend'].poll() is not None:
                print("❌ Backend failed to start!")
                sys.exit(1)
            
            # Start frontend
            self.start_frontend()
            
            print("\n✅ All services are running!")
            print("   Supabase Studio: http://localhost:54323")
            print("   Backend:  http://localhost:8000")
            print("   Frontend: http://localhost:8080")
            print("\n📌 Press Ctrl+C to stop all services\n")
            
            # Wait for processes
            while True:
                # Check if any process has died
                for name, process in self.processes.items():
                    if process and process.poll() is not None:
                        print(f"\n⚠️  {name} has stopped unexpectedly!")
                        self.cleanup()
                time.sleep(1)
                
        except Exception as e:
            print(f"\n❌ Error: {e}")
            self.cleanup()

if __name__ == "__main__":
    manager = ServiceManager()
    manager.run()