import sys
import os

# Добавляем корневую директорию проекта в sys.path,
# чтобы тесты могли импортировать модули из src/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))