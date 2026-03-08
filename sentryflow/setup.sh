#!/bin/bash

# ==========================================
# SentryFlow Setup Script
# ==========================================

set -e  # Exit on error

echo "=========================================="
echo "🛡️  SentryFlow Setup Script"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check Python version
echo "📋 Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Found Python $python_version"

# Check if MySQL is installed
echo ""
echo "📋 Checking MySQL..."
if command -v mysql &> /dev/null; then
    mysql_version=$(mysql --version | awk '{print $3}')
    echo -e "${GREEN}✓${NC} MySQL found: $mysql_version"
else
    echo -e "${RED}✗${NC} MySQL not found. Please install MySQL 8.0+ first."
    exit 1
fi

# Create virtual environment
echo ""
echo "📦 Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo -e "${GREEN}✓${NC} Virtual environment created"
else
    echo -e "${YELLOW}ℹ${NC} Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "🔄 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo ""
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo ""
echo "📦 Installing Python dependencies..."
echo "This may take a few minutes..."
pip install -r requirements.txt

# Create .env file if it doesn't exist
echo ""
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file..."
    cp .env.example .env
    echo -e "${GREEN}✓${NC} .env file created"
    echo -e "${YELLOW}⚠${NC}  Please edit .env and update your database credentials"
else
    echo -e "${YELLOW}ℹ${NC} .env file already exists"
fi

# Database setup
echo ""
read -p "Would you like to set up the database now? (y/n): " setup_db

if [ "$setup_db" = "y" ] || [ "$setup_db" = "Y" ]; then
    echo ""
    echo "🗄️  Setting up database..."
    read -p "Enter MySQL root password: " -s mysql_password
    echo ""
    
    # Check if database exists
    if mysql -u root -p"$mysql_password" -e "USE sentryflow;" 2>/dev/null; then
        echo -e "${YELLOW}⚠${NC}  Database 'sentryflow' already exists"
        read -p "Drop and recreate? (y/n): " recreate
        
        if [ "$recreate" = "y" ] || [ "$recreate" = "Y" ]; then
            echo "Dropping existing database..."
            mysql -u root -p"$mysql_password" -e "DROP DATABASE sentryflow;"
            echo "Creating database from schema..."
            mysql -u root -p"$mysql_password" < schema.sql
            echo -e "${GREEN}✓${NC} Database recreated successfully"
        fi
    else
        echo "Creating database from schema..."
        mysql -u root -p"$mysql_password" < schema.sql
        echo -e "${GREEN}✓${NC} Database created successfully"
    fi
    
    # Update .env with password
    if [ ! -z "$mysql_password" ]; then
        sed -i.bak "s/DB_PASSWORD=yourpassword/DB_PASSWORD=$mysql_password/" .env
        rm .env.bak
        echo -e "${GREEN}✓${NC} .env updated with database password"
    fi
else
    echo -e "${YELLOW}ℹ${NC} Skipping database setup"
    echo "Run manually with: mysql -u root -p < schema.sql"
fi

# Create log directory
echo ""
echo "📁 Setting up directories..."
mkdir -p logs
echo -e "${GREEN}✓${NC} Log directory created"

# Test import
echo ""
echo "🧪 Testing imports..."
python3 -c "from database import Database; from guardrail import guardrail; print('All imports successful!')" 2>&1
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} All modules imported successfully"
else
    echo -e "${RED}✗${NC} Import test failed"
    exit 1
fi

# Success message
echo ""
echo "=========================================="
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo "=========================================="
echo ""
echo "📝 Next steps:"
echo ""
echo "1. Activate the virtual environment:"
echo "   source venv/bin/activate"
echo ""
echo "2. Start the web interface:"
echo "   streamlit run streamlit_app.py"
echo ""
echo "3. Or use the command line:"
echo "   python main.py"
echo ""
echo "📚 For more information, see README.md"
echo ""
echo "🛡️  SentryFlow - Protecting AI Agents!"
echo "=========================================="
