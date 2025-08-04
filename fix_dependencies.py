#!/usr/bin/env python3
"""
Install missing dependencies for the adaptive bot.
"""
import subprocess
import sys

def install_dependencies():
    """Install missing optimization libraries."""
    dependencies = [
        'scikit-optimize',  # For Bayesian optimization
        'deap',            # For genetic algorithms
        'ta-lib',          # For technical analysis (if needed)
        'plotly',          # For visualization
        'dash',            # For web dashboard
    ]
    
    print("🔧 Installing missing dependencies...")
    
    for dep in dependencies:
        try:
            print(f"Installing {dep}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', dep])
            print(f"✅ {dep} installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install {dep}: {e}")
        except Exception as e:
            print(f"❌ Error installing {dep}: {e}")
    
    print("✅ Dependency installation complete!")

if __name__ == "__main__":
    install_dependencies()