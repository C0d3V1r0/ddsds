package collector

import (
	"bufio"
	"io"
	"log"
	"os"
	"path/filepath"
	"time"
)

// - Запись лога: источник, строка, путь к файлу
type LogEntry struct {
	Source string `json:"source"`
	Line   string `json:"line"`
	File   string `json:"file"`
}

// - Tailer следит за набором файлов и отправляет новые строки в канал
type LogTailer struct {
	files   []string
	entries chan LogEntry
}

// - Создание нового LogTailer с буферизированным каналом
func NewLogTailer(files []string) *LogTailer {
	return &LogTailer{
		files:   files,
		entries: make(chan LogEntry, 1000),
	}
}

// - Канал для чтения новых записей лога
func (lt *LogTailer) Entries() <-chan LogEntry {
	return lt.entries
}

// - Запуск горутин для отслеживания каждого файла
func (lt *LogTailer) Start() {
	for _, f := range lt.files {
		go lt.tailFile(f)
	}
}

// - Отслеживание одного файла: seek в конец, чтение новых строк
func (lt *LogTailer) tailFile(path string) {
	source := detectSource(path)
	for {
		f, err := os.Open(path)
		if err != nil {
			log.Printf("// - Не удалось открыть %s: %v", path, err)
			time.Sleep(5 * time.Second)
			continue
		}
		// - Переходим в конец файла, читаем только новые строки
		if _, err := f.Seek(0, io.SeekEnd); err != nil {
			log.Printf("// - Seek ошибка %s: %v", path, err)
			f.Close()
			continue
		}
		reader := bufio.NewReader(f)
		for {
			line, err := reader.ReadString('\n')
			if err != nil {
				if err == io.EOF {
					time.Sleep(200 * time.Millisecond)
					continue
				}
				break
			}
			if len(line) > 1 {
				lt.entries <- LogEntry{
					Source: source,
					Line:   line[:len(line)-1],
					File:   path,
				}
			}
		}
		f.Close()
		time.Sleep(1 * time.Second)
	}
}

// - Определение источника лога по имени/пути файла
func detectSource(path string) string {
	base := filepath.Base(path)
	switch {
	case base == "auth.log":
		return "auth"
	case filepath.Dir(path) == "/var/log/nginx" || base == "access.log" || base == "error.log":
		return "nginx"
	default:
		return "syslog"
	}
}
