#!/bin/bash

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' 

echo -e "${BLUE}🚁 Запуск DroneDelivery...${NC}\n"


if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python3 не найден. Установите Python3.${NC}"
    exit 1
fi


if [ ! -d "backend/venv" ]; then
    echo -e "${YELLOW}⚠️  Виртуальное окружение не найдено. Создаю...${NC}"
    cd backend
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    cd ..
    echo -e "${GREEN}✅ Виртуальное окружение создано и зависимости установлены${NC}\n"
fi


cleanup() {
    echo -e "\n${YELLOW}🛑 Остановка серверов...${NC}"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 0
}


trap cleanup SIGINT SIGTERM


echo -e "${BLUE}🔧 Запуск бэкенда (FastAPI)...${NC}"
cd backend
source venv/bin/activate


if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  Файл .env не найден.${NC}"
    echo -e "${YELLOW}Запустите скрипт настройки базы данных:${NC}"
    echo -e "${BLUE}   ../setup_db.sh${NC}\n"
    echo -e "${YELLOW}Или создайте .env файл вручную с правильным DATABASE_URL${NC}\n"
    exit 1
fi


echo -e "${BLUE}🔍 Проверка подключения к базе данных...${NC}"
DATABASE_URL=$(grep DATABASE_URL .env | cut -d '=' -f2- | tr -d '"' | tr -d "'")
if [ -z "$DATABASE_URL" ]; then
    echo -e "${RED}❌ DATABASE_URL не найден в .env файле${NC}"
    exit 1
fi


EXISTING_BACKEND_PID=$(lsof -ti:8000 2>/dev/null | head -1)
if [ -n "$EXISTING_BACKEND_PID" ]; then
    echo -e "${YELLOW}⚠️  Бэкенд уже запущен на порту 8000 (PID: $EXISTING_BACKEND_PID)${NC}"
    echo -e "${BLUE}   Используем существующий процесс${NC}"
    BACKEND_PID=$EXISTING_BACKEND_PID
    cd ..
else
    echo -e "${BLUE}🚀 Запускаю новый бэкенд...${NC}"
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level error > /dev/null 2>&1 &
    BACKEND_PID=$!
    cd ..
    
    sleep 2
    
    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Бэкенд запущен (PID: $BACKEND_PID) на http://localhost:8000${NC}"
    else
        echo -e "${RED}❌ Ошибка запуска бэкенда${NC}"
        exit 1
    fi
fi

echo -e "${BLUE}   📚 Документация API: http://localhost:8000/docs${NC}\n"


echo -e "${BLUE}🎨 Запуск фронтенда...${NC}"


FRONTEND_PORT=3000

EXISTING_FRONTEND_PID=$(lsof -ti:$FRONTEND_PORT 2>/dev/null | head -1)
if [ -n "$EXISTING_FRONTEND_PID" ]; then
    echo -e "${YELLOW}⚠️  Фронтенд уже запущен на порту $FRONTEND_PORT (PID: $EXISTING_FRONTEND_PID)${NC}"
    echo -e "${BLUE}   Используем существующий процесс${NC}"
    FRONTEND_PID=$EXISTING_FRONTEND_PID
else
    while lsof -Pi :$FRONTEND_PORT -sTCP:LISTEN -t >/dev/null 2>&1; do
        echo -e "${YELLOW}⚠️  Порт $FRONTEND_PORT занят, пробую следующий...${NC}"
        FRONTEND_PORT=$((FRONTEND_PORT + 1))
    done
    
    echo -e "${BLUE}🚀 Запускаю фронтенд на порту $FRONTEND_PORT...${NC}"
    python3 -m http.server $FRONTEND_PORT > /dev/null 2>&1 &
    FRONTEND_PID=$!
fi


if [ -z "$EXISTING_FRONTEND_PID" ]; then
    sleep 1
    
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Фронтенд запущен (PID: $FRONTEND_PID) на http://localhost:$FRONTEND_PORT${NC}\n"
    else
        echo -e "${RED}❌ Ошибка запуска фронтенда${NC}"
        if [ -z "$EXISTING_BACKEND_PID" ]; then
            kill $BACKEND_PID 2>/dev/null
        fi
        exit 1
    fi
else
    echo -e "${GREEN}✅ Фронтенд уже запущен (PID: $FRONTEND_PID) на http://localhost:$FRONTEND_PORT${NC}\n"
fi

echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${GREEN}✅ Все серверы запущены!${NC}"
echo -e "${GREEN}════════════════════════════════════════${NC}"
echo -e "${BLUE}🌐 Фронтенд: http://localhost:$FRONTEND_PORT${NC}"
echo -e "${BLUE}🔧 Бэкенд API: http://localhost:8000${NC}"
echo -e "${BLUE}📚 API Документация: http://localhost:8000/docs${NC}"
echo -e "${YELLOW}💡 Нажмите Ctrl+C для остановки${NC}\n"


wait

