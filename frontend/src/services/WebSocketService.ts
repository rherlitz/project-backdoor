import Phaser from 'phaser';

// Define command/message structures locally for now
// TODO: Move these to a dedicated models file (e.g., src/models/commands.ts)
interface IncomingMessage {
    type: string; // e.g., 'description', 'dialogue', 'error', 'state_update'
    payload: any;
}

interface OutgoingCommand {
    command: string;
    payload: any;
}

const WEBSOCKET_URL = 'ws://localhost:8000/ws'; // Backend WebSocket URL

class WebSocketService extends Phaser.Events.EventEmitter {
    private ws: WebSocket | null = null;
    private connectionPromise: Promise<void> | null = null;
    private resolveConnectionPromise: (() => void) | null = null;
    private rejectConnectionPromise: ((reason?: any) => void) | null = null;
    private reconnectAttempts: number = 0;
    private maxReconnectAttempts: number = 5;
    private reconnectDelay: number = 3000; // 3 seconds
    private reconnectTimeoutId: number | undefined = undefined; // Store timeout ID

    constructor() {
        super();
    }

    connect(): Promise<void> {
        // Clear any pending reconnect timeout before attempting new connection
        if (this.reconnectTimeoutId) {
            clearTimeout(this.reconnectTimeoutId);
            this.reconnectTimeoutId = undefined;
        }

        if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
            console.log('[WS] Already connected or connecting.');
            return this.connectionPromise || Promise.resolve();
        }

        console.log(`[WS] Attempting to connect to ${WEBSOCKET_URL}... (Attempt ${this.reconnectAttempts + 1})`);

        // Create a new promise for this connection attempt
        this.connectionPromise = new Promise((resolve, reject) => {
            this.resolveConnectionPromise = resolve;
            this.rejectConnectionPromise = reject;
        });

        try {
            this.ws = new WebSocket(WEBSOCKET_URL);
            this.setupEventListeners();
        } catch (error) {
            console.error('[WS] Connection failed immediately:', error);
            this.emit('disconnected');
            if (this.rejectConnectionPromise) {
                this.rejectConnectionPromise(error);
            }
            this.scheduleReconnect();
        }

        return this.connectionPromise;
    }

    private setupEventListeners(): void {
        if (!this.ws) return;

        this.ws.onopen = () => {
            console.log('[WS] Connection established.');
            this.reconnectAttempts = 0; // Reset on successful connection
            this.emit('connected');
            if (this.resolveConnectionPromise) {
                this.resolveConnectionPromise();
            }
            // Reset promise handlers after resolution
            this.resolveConnectionPromise = null;
            this.rejectConnectionPromise = null;
        };

        this.ws.onmessage = (event) => {
            try {
                const message: IncomingMessage = JSON.parse(event.data);
                console.log('[WS] Message received:', message);
                // Emit specific event based on message type
                this.emit('message', message); // Generic message event
                this.emit(message.type, message.payload); // Specific event type (e.g., 'description', 'error')
            } catch (error) {
                console.error('[WS] Failed to parse message:', event.data, error);
            }
        };

        this.ws.onerror = (event) => {
            console.error('[WS] Error:', event);
            this.emit('error', event);
            // Reject the promise if the connection hasn't opened yet
            if (this.rejectConnectionPromise) {
                this.rejectConnectionPromise(new Error('WebSocket error during connection attempt'));
                 this.resolveConnectionPromise = null;
                 this.rejectConnectionPromise = null;
            }
        };

        this.ws.onclose = (event) => {
            console.warn(`[WS] Connection closed. Code: ${event.code}, Reason: ${event.reason}, Clean: ${event.wasClean}`);
            const wasConnected = !!this.ws; // Check if it was previously connected
            this.ws = null;
            this.emit('disconnected');
            // Reject the promise only if it was pending (i.e., initial connection failed)
            if (this.rejectConnectionPromise) {
                 this.rejectConnectionPromise(new Error(`WebSocket closed with code ${event.code}`));
                 this.resolveConnectionPromise = null;
                 this.rejectConnectionPromise = null;
            }
            // Only schedule reconnect if it wasn't a clean disconnect requested by client
            if (event.code !== 1000) { 
                this.scheduleReconnect();
            }
        };
    }

    private scheduleReconnect(): void {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error(`[WS] Max reconnect attempts (${this.maxReconnectAttempts}) reached. Giving up.`);
            return;
        }

        // Don't schedule if already scheduled
        if (this.reconnectTimeoutId) {
            return;
        }

        this.reconnectAttempts++;
        // Exponential backoff, but cap delay to avoid excessively long waits (e.g., 30s max)
        const delay = Math.min(this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts -1), 30000); 
        console.log(`[WS] Scheduling reconnect attempt ${this.reconnectAttempts} in ${delay / 1000} seconds...`);

        this.reconnectTimeoutId = setTimeout(() => {
            this.reconnectTimeoutId = undefined;
            this.connect();
        }, delay);
    }

    isConnected(): boolean {
        return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
    }

    async sendCommand(command: string, payload: any = {}): Promise<void> {
        // Wait for connection if it's not established yet
        if (!this.isConnected()) {
            console.log('[WS] Connection not established. Waiting...');
            if (!this.connectionPromise || this.ws?.readyState === WebSocket.CLOSED) {
                // Attempt to connect if not already trying or if closed
                console.log('[WS] Triggering connection attempt before sending...');
                this.connect();
            }
            try {
                await this.connectionPromise; // Wait for the current/new connection attempt
                console.log('[WS] Connection ready. Proceeding to send command.');
            } catch (error) {
                console.error('[WS] Failed to connect before sending command:', error);
                this.emit('error', { message: 'Failed to connect to server to send command.' });
                return; // Don't send if connection failed
            }
        }

        // Double-check connection status after potentially waiting
        if (this.isConnected()) {
            const message: OutgoingCommand = { command, payload };
            try {
                console.log('[WS] Sending command:', message);
                this.ws?.send(JSON.stringify(message));
            } catch (error) {
                console.error('[WS] Failed to send message:', error);
                this.emit('error', { message: 'Failed to send command via WebSocket.' });
            }
        } else {
             console.error('[WS] Cannot send command, WebSocket is not connected after wait.');
             this.emit('error', { message: 'Cannot send command, WebSocket is not connected.' });
        }
    }

    disconnect(reason: string = 'Client request'): void {
        // Clear any pending reconnect timeouts
         if (this.reconnectTimeoutId) {
            clearTimeout(this.reconnectTimeoutId);
            this.reconnectTimeoutId = undefined;
        }
        this.reconnectAttempts = this.maxReconnectAttempts; // Prevent further automatic reconnections

        if (this.ws) {
            console.log(`[WS] Manually disconnecting... Reason: ${reason}`);
            this.ws.close(1000, reason); // Normal closure
            this.ws = null;
        }
        this.emit('disconnected');
    }
}

// Export a singleton instance
export const webSocketService = new WebSocketService(); 