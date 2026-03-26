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

// - Ограничение частоты выполнения команд (token bucket)
const maxCommandsPerSecond = 10

var (
	commandTokens   = maxCommandsPerSecond
	lastCommandTime = time.Now()
	commandMu       sync.Mutex
)

// - Проверяет, можно ли выполнить команду с учётом rate limit
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

type Client struct {
	url            string
	secret         string
	tlsSkipVerify  bool
	conn           *websocket.Conn
	mu             sync.Mutex
	writeMu        sync.Mutex // - защита от конкурентной записи в websocket (gorilla запрещает)
	connected      bool
	buffer         *buffer.RingBuffer
	heartbeatDone  chan struct{} // - сигнал остановки горутины heartbeat
	onCommand      func(id string, command string, params map[string]interface{})
}

func NewClient(url, secret string, tlsSkipVerify bool, onCommand func(string, string, map[string]interface{})) *Client {
	return &Client{
		url:           url,
		secret:        secret,
		tlsSkipVerify: tlsSkipVerify,
		buffer:        buffer.New(1000),
		onCommand:     onCommand,
	}
}

func (c *Client) Run() {
	for {
		err := c.connect()
		if err != nil {
			log.Printf("// - Ошибка подключения WS: %v", err)
		}
		c.reconnect()
	}
}

func (c *Client) connect() error {
	// - Настраиваем TLS: минимум TLS 1.2, опциональный skip verify для dev-окружения
	dialer := websocket.Dialer{
		TLSClientConfig: &tls.Config{
			InsecureSkipVerify: c.tlsSkipVerify,
			MinVersion:         tls.VersionTLS12,
		},
		HandshakeTimeout: 10 * time.Second,
	}

	// - Аутентификация: передаём секрет в HTTP-заголовке и первом сообщении (обратная совместимость)
	headers := http.Header{}
	headers.Set("Authorization", "Bearer "+c.secret)
	conn, _, err := dialer.Dial(c.url, headers)
	if err != nil {
		return fmt.Errorf("dial: %w", err)
	}
	c.mu.Lock()
	c.conn = conn
	c.mu.Unlock()

	// - Также отправляем auth-сообщение для совместимости со старым сервером
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
	log.Println("// - Подключен к API")

	// - Отправляем буферизованные сообщения с проверкой ошибок
	buffered := c.buffer.DrainAll()
	for i, msg := range buffered {
		c.writeMu.Lock()
		err := conn.WriteMessage(websocket.TextMessage, msg)
		c.writeMu.Unlock()
		if err != nil {
			// - Возвращаем неотправленные сообщения обратно в буфер
			for j := i; j < len(buffered); j++ {
				c.buffer.Push(buffered[j])
			}
			break
		}
	}

	// - Останавливаем предыдущий heartbeat если был, и запускаем новый
	c.heartbeatDone = make(chan struct{})
	go c.heartbeat()

	// - Цикл чтения команд от API
	for {
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
			// - Проверяем rate limit перед выполнением команды
			if !canExecuteCommand() {
				log.Printf("// - Команда %s отклонена: превышен rate limit", id)
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

	// - Останавливаем heartbeat перед выходом из connect
	close(c.heartbeatDone)

	c.mu.Lock()
	c.connected = false
	c.conn = nil
	c.mu.Unlock()
	return nil
}

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
			// - Получен сигнал остановки, завершаем горутину
			return
		}
	}
}

func (c *Client) reconnect() {
	delay := time.Second
	for {
		log.Printf("// - Реконнект через %v...", delay)
		time.Sleep(delay)
		err := c.connect()
		if err == nil {
			return
		}
		log.Printf("// - Реконнект не удался: %v", err)
		delay *= 2
		if delay > 60*time.Second {
			delay = 60 * time.Second
		}
	}
}

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

func (c *Client) SendDisconnect() {
	c.mu.Lock()
	conn := c.conn
	c.mu.Unlock()
	if conn == nil {
		return
	}
	// - Отправляем буферизованные сообщения перед отключением
	buffered := c.buffer.DrainAll()
	for _, msg := range buffered {
		c.writeMu.Lock()
		if err := conn.WriteMessage(websocket.TextMessage, msg); err != nil {
			c.writeMu.Unlock()
			log.Printf("// - Ошибка отправки буферизованного сообщения при disconnect: %v", err)
			break
		}
		c.writeMu.Unlock()
	}
	c.writeMu.Lock()
	if err := conn.WriteJSON(map[string]string{"type": "disconnect", "reason": "shutdown"}); err != nil {
		log.Printf("// - Ошибка отправки disconnect: %v", err)
	}
	c.writeMu.Unlock()
	conn.Close()
}
