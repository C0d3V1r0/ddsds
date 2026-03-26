package ws

import (
	"crypto/tls"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"github.com/nullius/agent/buffer"
)

// Лимит команд в секунду — простой token bucket, чтобы сервер не задавил агента пачкой команд
const maxCommandsPerSecond = 10

var (
	commandTokens   = maxCommandsPerSecond
	lastCommandTime = time.Now()
	commandMu       sync.Mutex
)

// canExecuteCommand проверяет, не превышен ли rate limit на выполнение команд.
// Пополняет токены пропорционально прошедшему времени.
func canExecuteCommand() bool {
	commandMu.Lock()
	defer commandMu.Unlock()
	now := time.Now()
	elapsed := now.Sub(lastCommandTime).Seconds()
	commandTokens += int(elapsed * float64(maxCommandsPerSecond))
	if commandTokens > maxCommandsPerSecond {
		commandTokens = maxCommandsPerSecond
	}
	lastCommandTime = now
	if commandTokens <= 0 {
		return false
	}
	commandTokens--
	return true
}

// Client — WebSocket-клиент агента. Держит постоянное соединение с API-сервером,
// отправляет телеметрию и принимает команды (block_ip, kill_process и т.д.).
// При обрыве переподключается с экспоненциальным backoff.
type Client struct {
	url           string
	secret        string
	tlsSkipVerify bool
	conn          *websocket.Conn
	mu            sync.Mutex
	writeMu       sync.Mutex // gorilla/websocket не потокобезопасен на запись — нужен отдельный мьютекс
	connected     bool
	buffer        *buffer.RingBuffer // кольцевой буфер для сообщений, накопленных офлайн
	heartbeatDone chan struct{}
	done          chan struct{}
	closeOnce     sync.Once
	onCommand     func(id string, command string, params map[string]interface{})
}

func NewClient(url, secret string, tlsSkipVerify bool, onCommand func(string, string, map[string]interface{})) *Client {
	return &Client{
		url:           url,
		secret:        secret,
		tlsSkipVerify: tlsSkipVerify,
		buffer:        buffer.New(1000),
		done:          make(chan struct{}),
		onCommand:     onCommand,
	}
}

// Run — основной цикл: подключение → чтение → реконнект. Блокирует горутину.
// Backoff: 1с → 2с → 4с → ... → 60с (максимум)
func (c *Client) Run() {
	delay := time.Second
	for {
		select {
		case <-c.done:
			return
		default:
		}

		err := c.connect()
		if err == nil {
			delay = time.Second
		} else {
			log.Printf("Ошибка подключения WS: %v", err)
		}

		log.Printf("Реконнект через %v...", delay)
		select {
		case <-c.done:
			return
		case <-time.After(delay):
		}
		if delay < 60*time.Second {
			delay *= 2
			if delay > 60*time.Second {
				delay = 60 * time.Second
			}
		}
	}
}

// connect устанавливает WS-соединение, проходит аутентификацию,
// сбрасывает накопленный буфер и входит в цикл чтения команд.
func (c *Client) connect() error {
	// TLS: минимум 1.2, skip verify только для dev-стенда
	dialer := websocket.Dialer{
		TLSClientConfig: &tls.Config{
			InsecureSkipVerify: c.tlsSkipVerify,
			MinVersion:         tls.VersionTLS12,
		},
		HandshakeTimeout: 10 * time.Second,
	}

	// Секрет передаём и в заголовке, и в первом сообщении — обратная совместимость
	headers := http.Header{}
	headers.Set("Authorization", "Bearer "+c.secret)
	conn, _, err := dialer.Dial(c.url, headers)
	if err != nil {
		return fmt.Errorf("dial: %w", err)
	}
	c.mu.Lock()
	c.conn = conn
	c.mu.Unlock()

	// Auth-сообщение для старых версий сервера, которые не читают заголовок
	auth := map[string]string{"type": "auth", "secret": c.secret}
	c.writeMu.Lock()
	err = conn.WriteJSON(auth)
	c.writeMu.Unlock()
	if err != nil {
		conn.Close()
		return fmt.Errorf("auth send: %w", err)
	}

	var resp map[string]interface{}
	if err := conn.ReadJSON(&resp); err != nil {
		conn.Close()
		return fmt.Errorf("auth read: %w", err)
	}
	if resp["type"] != "auth_ok" {
		conn.Close()
		return fmt.Errorf("auth failed: %v", resp)
	}

	c.mu.Lock()
	c.connected = true
	c.mu.Unlock()
	log.Println("Подключен к API-серверу")

	// Отправляем то, что накопилось в буфере за время офлайна
	buffered := c.buffer.DrainAll()
	for i, msg := range buffered {
		c.writeMu.Lock()
		err := conn.WriteMessage(websocket.TextMessage, msg)
		c.writeMu.Unlock()
		if err != nil {
			// Не смогли отправить — возвращаем остаток обратно в буфер
			for j := i; j < len(buffered); j++ {
				c.buffer.Push(buffered[j])
			}
			break
		}
	}

	// Heartbeat — пинг каждые 15с, чтобы соединение не убил прокси/NAT
	c.heartbeatDone = make(chan struct{})
	go c.heartbeat()

	// Основной цикл чтения входящих команд от сервера
	for {
		select {
		case <-c.done:
			close(c.heartbeatDone)
			c.mu.Lock()
			c.connected = false
			c.conn = nil
			c.mu.Unlock()
			return nil
		default:
		}
		_, raw, err := conn.ReadMessage()
		if err != nil {
			break
		}
		var msg map[string]interface{}
		if json.Unmarshal(raw, &msg) != nil {
			continue
		}
		if msg["type"] == "pong" {
			continue
		}
		if id, ok := msg["id"].(string); ok {
			if !canExecuteCommand() {
				log.Printf("Команда %s отклонена: превышен rate limit", id)
				c.SendResult(id, "error", "rate limit exceeded")
				continue
			}
			cmd, _ := msg["command"].(string)
			params, _ := msg["params"].(map[string]interface{})
			if c.onCommand != nil {
				c.onCommand(id, cmd, params)
			}
		}
	}

	close(c.heartbeatDone)

	c.mu.Lock()
	c.connected = false
	c.conn = nil
	c.mu.Unlock()
	return nil
}

// heartbeat отправляет ping каждые 15 секунд, пока соединение живо
func (c *Client) heartbeat() {
	ticker := time.NewTicker(15 * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ticker.C:
			c.mu.Lock()
			conn := c.conn
			connected := c.connected
			c.mu.Unlock()
			if !connected || conn == nil {
				return
			}
			ping := map[string]string{"type": "ping"}
			c.writeMu.Lock()
			err := conn.WriteJSON(ping)
			c.writeMu.Unlock()
			if err != nil {
				return
			}
		case <-c.heartbeatDone:
			return
		case <-c.done:
			return
		}
	}
}

// Send отправляет сообщение на сервер. Если нет соединения — кладёт в кольцевой буфер.
func (c *Client) Send(msg interface{}) error {
	data, err := json.Marshal(msg)
	if err != nil {
		return err
	}
	c.mu.Lock()
	conn := c.conn
	connected := c.connected
	c.mu.Unlock()

	if !connected || conn == nil {
		c.buffer.Push(data)
		return nil
	}
	c.writeMu.Lock()
	err = conn.WriteMessage(websocket.TextMessage, data)
	c.writeMu.Unlock()
	if err != nil {
		c.buffer.Push(data)
	}
	return err
}

// SendResult отправляет результат выполнения команды обратно на сервер
func (c *Client) SendResult(id, status, errMsg string) {
	result := map[string]string{
		"type":   "command_result",
		"id":     id,
		"status": status,
	}
	if errMsg != "" {
		result["error"] = errMsg
	}
	c.Send(result)
}

// SendDisconnect — корректное завершение: сбрасываем буфер и шлём disconnect
func (c *Client) SendDisconnect() {
	c.mu.Lock()
	conn := c.conn
	c.mu.Unlock()
	if conn == nil {
		return
	}
	// Перед отключением пытаемся отправить всё, что накопилось
	buffered := c.buffer.DrainAll()
	for _, msg := range buffered {
		c.writeMu.Lock()
		if err := conn.WriteMessage(websocket.TextMessage, msg); err != nil {
			c.writeMu.Unlock()
			log.Printf("Ошибка отправки буфера при disconnect: %v", err)
			break
		}
		c.writeMu.Unlock()
	}
	c.writeMu.Lock()
	if err := conn.WriteJSON(map[string]string{"type": "disconnect", "reason": "shutdown"}); err != nil {
		log.Printf("Ошибка отправки disconnect: %v", err)
	}
	c.writeMu.Unlock()
	conn.Close()
}

// Close останавливает клиента и закрывает соединение. Безопасен для повторного вызова.
func (c *Client) Close() {
	c.closeOnce.Do(func() {
		close(c.done)
		c.mu.Lock()
		conn := c.conn
		c.connected = false
		c.conn = nil
		c.mu.Unlock()
		if conn != nil {
			_ = conn.Close()
		}
	})
}
