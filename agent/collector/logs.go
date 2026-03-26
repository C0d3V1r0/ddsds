package collector

import (
	"bufio"
	"io"
	"log"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// LogEntry — одна строка лога с определённым источником (auth, nginx, syslog)
type LogEntry struct {
	Source string `json:"source"`
	Line   string `json:"line"`
	File   string `json:"file"`
}

// LogTailer следит за списком файлов и стримит новые строки в канал.
// На каждый файл запускается отдельная горутина. Работает как tail -f.
type LogTailer struct {
	files   []string
	entries chan LogEntry
	done    chan struct{}
	once    sync.Once
}

// NewLogTailer создаёт tailer с буфером на 1000 строк — при переполнении новые строки блокируются
func NewLogTailer(files []string) *LogTailer {
	return &LogTailer{
		files:   files,
		entries: make(chan LogEntry, 1000),
		done:    make(chan struct{}),
	}
}

// Entries возвращает канал для чтения новых записей лога
func (lt *LogTailer) Entries() <-chan LogEntry {
	return lt.entries
}

// Start запускает горутину tail-а для каждого файла из конфига
func (lt *LogTailer) Start() {
	for _, f := range lt.files {
		go lt.tailFile(f)
	}
}

// Stop останавливает все горутины. Безопасен для повторного вызова.
func (lt *LogTailer) Stop() {
	lt.once.Do(func() {
		close(lt.done)
	})
}

// tailFile — цикл отслеживания одного файла. Сначала seekим в конец (нас интересуют
// только новые строки), потом поллим каждые 200мс. Если файл пропал — ждём 5с и пробуем снова.
func (lt *LogTailer) tailFile(path string) {
	source := detectSource(path)
	for {
		select {
		case <-lt.done:
			return
		default:
		}
		f, err := os.Open(path)
		if err != nil {
			log.Printf("Не удалось открыть %s: %v", path, err)
			select {
			case <-lt.done:
				return
			case <-time.After(5 * time.Second):
			}
			continue
		}
		// Перематываем в конец — старые строки не нужны
		if _, err := f.Seek(0, io.SeekEnd); err != nil {
			log.Printf("Seek ошибка %s: %v", path, err)
			f.Close()
			select {
			case <-lt.done:
				return
			default:
			}
			continue
		}
		reader := bufio.NewReader(f)
		for {
			select {
			case <-lt.done:
				f.Close()
				return
			default:
			}
			line, err := reader.ReadString('\n')
			if err != nil {
				if err == io.EOF {
					select {
					case <-lt.done:
						f.Close()
						return
					case <-time.After(200 * time.Millisecond):
					}
					continue
				}
				break
			}
			if len(line) > 1 {
				entry := LogEntry{
					Source: source,
					Line:   line[:len(line)-1],
					File:   path,
				}
				select {
				case <-lt.done:
					f.Close()
					return
				case lt.entries <- entry:
				}
			}
		}
		f.Close()
		select {
		case <-lt.done:
			return
		case <-time.After(1 * time.Second):
		}
	}
}

// detectSource определяет категорию лога по пути: auth.log → "auth",
// всё из /var/log/nginx/ → "nginx", остальное → "syslog"
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
