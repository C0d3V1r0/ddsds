package buffer

import "sync"

// - потокобезопасный кольцевой буфер для накопления данных перед отправкой
type RingBuffer struct {
	mu    sync.Mutex
	items [][]byte
	head  int
	count int
	cap   int
}

// - создаёт кольцевой буфер заданной ёмкости; паникует при некорректном capacity
func New(capacity int) *RingBuffer {
	if capacity <= 0 {
		panic("buffer capacity must be > 0")
	}
	return &RingBuffer{
		items: make([][]byte, capacity),
		cap:   capacity,
	}
}

// - добавляет элемент в буфер, при переполнении затирает самый старый
func (rb *RingBuffer) Push(data []byte) {
	rb.mu.Lock()
	defer rb.mu.Unlock()

	idx := (rb.head + rb.count) % rb.cap
	if rb.count == rb.cap {
		// - буфер полон — сдвигаем голову, теряем самый старый элемент
		rb.head = (rb.head + 1) % rb.cap
	} else {
		rb.count++
	}
	rb.items[idx] = data
}

// - извлекает все элементы из буфера и очищает его
func (rb *RingBuffer) DrainAll() [][]byte {
	rb.mu.Lock()
	defer rb.mu.Unlock()

	result := make([][]byte, 0, rb.count)
	for i := 0; i < rb.count; i++ {
		idx := (rb.head + i) % rb.cap
		result = append(result, rb.items[idx])
	}

	rb.head = 0
	rb.count = 0
	return result
}
