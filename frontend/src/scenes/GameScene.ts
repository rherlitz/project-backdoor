import Phaser from 'phaser';
import { webSocketService } from '../services/WebSocketService';

export default class GameScene extends Phaser.Scene {
    private descriptionText!: Phaser.GameObjects.Text;
    private player!: Phaser.Types.Physics.Arcade.SpriteWithDynamicBody;
    private clippy!: Phaser.GameObjects.Sprite;
    private playerMoveTween: Phaser.Tweens.Tween | null = null;
    private parserInput!: HTMLInputElement;

    constructor() {
        super('GameScene');
    }

    preload() {
        console.log('GameScene: preload');
        // Load game assets here (backgrounds, sprites, etc.)
        this.load.image('pod_interior_bg', 'assets/images/backgrounds/pod_interior.png');
        this.load.image('pod_exterior_bg', 'assets/images/backgrounds/pod_exterior.png');
        this.load.image('alley_bg', 'assets/images/backgrounds/alley.png');

        // !! IMPORTANT: Replace frameWidth/frameHeight with your actual frame dimensions !!
        const dexFrameWidth = 25;  // <-- Replace with actual width of one Dex frame
        const dexFrameHeight = 45; // <-- Replace with actual height of one Dex frame
        this.load.spritesheet('dex_sprite', 'assets/images/sprites/dex.png', {
            frameWidth: dexFrameWidth,
            frameHeight: dexFrameHeight
        });

        // !! IMPORTANT: Replace frameWidth/frameHeight with your actual frame dimensions !!
        const clippyFrameWidth = 32;  // <-- Replace with actual width of one Clippy frame
        const clippyFrameHeight = 33; // <-- Replace with actual height of one Clippy frame
        this.load.spritesheet('clippy_sprite', 'assets/images/sprites/clippy.png', {
            frameWidth: clippyFrameWidth,
            frameHeight: clippyFrameHeight
        });
    }

    create() {
        console.log('GameScene: create');

        // --- Basic Setup --- 
        const bg = this.add.image(this.cameras.main.centerX, this.cameras.main.centerY, 'pod_interior_bg');
        // Optional: Scale background to fit, maintain aspect ratio might be better depending on art
        bg.setDisplaySize(bg.width * 2, bg.height * 2);
        // bg.setDisplaySize(this.cameras.main.width, this.cameras.main.height);

        // --- Define Animations --- 
        // Dex animations (4x2 spritesheet = 8 frames total, 0-7)
        this.anims.create({
            key: 'dex_idle',
            frames: this.anims.generateFrameNumbers('dex_sprite', { start: 0, end: 2 }), // Use frames 0-3 for idle
            frameRate: 5, // Adjust frame rate as needed
            repeat: -1 // Loop forever
        });
        // Example walk animation (assuming frames 4-7 are for walking)
        this.anims.create({
            key: 'dex_walk',
            frames: this.anims.generateFrameNumbers('dex_sprite', { start: 4, end: 7 }),
            frameRate: 5,
            repeat: -1
        });

        // Clippy animations (3x3 spritesheet = 9 frames total, 0-8)
        this.anims.create({
            key: 'clippy_idle',
            frames: this.anims.generateFrameNumbers('clippy_sprite', { start: 0, end: 3 }), // Use all frames for idle animation
            frameRate: 8, // Adjust frame rate
            repeat: -1
        });

        // Set world bounds and make it same as the bg
        this.physics.world.setBounds(0, 0, bg.width, bg.height);

        // --- Player Setup --- 
        // Initial player position (example)
        const spriteScale = 4;

        this.player = this.physics.add.sprite(this.cameras.main.width * 0.5, this.cameras.main.height * 0.8, 'dex_sprite');
        this.player.setCollideWorldBounds(true); // Keep player within screen bounds
        this.player.setInteractive(); // Make player clickable if needed later
        this.player.setDisplaySize(this.player.width * spriteScale, this.player.height * spriteScale);
        this.player.body.setSize(this.player.width * 0.8, this.player.height * 0.8); // Adjust physics body size if needed
        this.player.anims.play('dex_idle'); // Play idle animation

        // --- NPC Setup --- 
        this.clippy = this.add.sprite(this.cameras.main.width * 0.6, this.cameras.main.height * 0.6, 'clippy_sprite');
        this.clippy.setDisplaySize(this.clippy.width * spriteScale, this.clippy.height * spriteScale);
        this.clippy.setInteractive(); // Make NPC clickable
        this.clippy.setData('id', 'npc_clippy');
        this.clippy.anims.play('clippy_idle'); // Play idle animation

        // --- Hotspot Setup --- 
        const terminalHotspot = this.add.rectangle(this.cameras.main.width * 0.8, this.cameras.main.height * 0.5, 50, 70); // x, y, width, height
        terminalHotspot.setInteractive();
        terminalHotspot.setData('id', 'object_terminal');
        // Optional: Make hotspot visible for debugging
        // terminalHotspot.setStrokeStyle(2, 0xff0000); 

        // List of interactive objects for hit testing
        const interactiveObjects = [this.clippy, terminalHotspot];

        // --- UI Text --- 
        this.descriptionText = this.add.text(10, 10, 'Click to move Dex.', {
            font: '10px Arial',
            color: '#ffffff',
            backgroundColor: 'rgba(0,0,0,0.5)', // Add background for readability
            padding: { x: 5, y: 3 },
            wordWrap: { width: this.cameras.main.width - 20 }
        }).setOrigin(0).setScrollFactor(0).setDepth(100); // Keep text fixed on screen

        // --- Input Handling (Disable Pointer Down) --- 
        // this.input.on(Phaser.Input.Events.POINTER_DOWN, ... ); // <-- Comment out or remove pointer input handler

        // --- Text Parser Setup --- 
        this.parserInput = document.getElementById('parser-input') as HTMLInputElement;
        if (!this.parserInput) {
            console.error('Parser input element not found!');
            return; 
        }

        // Focus input field initially
        this.parserInput.focus(); 

        // Add listener for Enter key
        this.parserInput.addEventListener('keydown', (event) => {
            if (event.key === 'Enter') {
                const inputText = this.parserInput.value.trim();
                if (inputText) {
                    this.parseAndSendCommand(inputText);
                    this.parserInput.value = ''; // Clear input
                }
            }
        });

        // Prevent Phaser from capturing keyboard events while typing
        this.input.keyboard?.disableGlobalCapture();
        this.parserInput.addEventListener('focus', () => {
            this.input.keyboard?.disableGlobalCapture();
        });
        this.parserInput.addEventListener('blur', () => {
            this.input.keyboard?.enableGlobalCapture();
        });

        // --- WebSocket Message Handling --- 
        webSocketService.on('description', this.handleDescription, this);
        webSocketService.on('error', this.handleError, this);
        webSocketService.on('dialogue', this.handleDialogue, this);
        // Add more listeners for other message types from backend (e.g., 'npc_move')

        // Clean up listeners when the scene shuts down
        this.events.on(Phaser.Scenes.Events.SHUTDOWN, () => {
            console.log('GameScene: Shutting down, removing WS listeners');
            webSocketService.off('description', this.handleDescription, this);
            webSocketService.off('error', this.handleError, this);
            webSocketService.off('dialogue', this.handleDialogue, this);
            this.stopPlayerMovement(); // Stop any movement tweens
        });

        console.log('GameScene setup complete. Ready for input.');
    }

    update(time: number, delta: number) {
        // Stop movement if tween is finished and velocity is low (prevents drifting)
        if (this.playerMoveTween && !this.playerMoveTween.isPlaying()) {
             if (this.player.body.velocity.lengthSq() < 1) { // Check if velocity is near zero
                this.stopPlayerMovement(false); // Stop physics body without interrupting tween (which is already done)
            }
        }
    }

    private movePlayerTo(targetX: number, targetY: number) {
        this.stopPlayerMovement(); // Stop previous tween/movement

        // Play walk animation if available, otherwise idle
        this.player.anims.play('dex_walk', true);

        const distance = Phaser.Math.Distance.Between(this.player.x, this.player.y, targetX, targetY);
        const speed = 100; // pixels per second
        const duration = (distance / speed) * 1000; // duration in milliseconds

        // Simple tween for movement - For complex maps, use pathfinding (e.g., EasyStar.js)
        this.playerMoveTween = this.tweens.add({
            targets: this.player,
            x: targetX,
            y: targetY,
            duration: duration,
            ease: 'Linear',
            onComplete: () => {
                this.stopPlayerMovement(false); // Ensure body stops on tween complete
                this.descriptionText.setText('Arrived. Click to move again.');
            },
            onUpdate: () => {
                 // Optional: Update player velocity based on tween direction for physics interactions
                 // This is a simple way; a more robust approach might directly control velocity.
                 const angle = Phaser.Math.Angle.Between(this.player.x, this.player.y, targetX, targetY);
                 this.physics.velocityFromRotation(angle, speed, this.player.body.velocity);
            }
        });
    }

    private stopPlayerMovement(stopTween: boolean = true) {
        if (stopTween && this.playerMoveTween && this.playerMoveTween.isPlaying()) {
            this.playerMoveTween.stop();
        }
        this.playerMoveTween = null; // Clear the tween reference
        
        if (this.player && this.player.body) {
             this.player.body.setVelocity(0, 0);
             // Play idle animation when stopping
             if (this.player.anims) { // Check if anims component exists
                this.player.anims.play('dex_idle', true);
             }
        }
    }

    private handleDescription(payload: any) {
        console.log('Received description:', payload.description);
        // Only update if not currently moving (to avoid overwriting movement status)
        if (!this.playerMoveTween || !this.playerMoveTween.isPlaying()) {
             if (payload.description) {
                 this.descriptionText.setText(`Description: ${payload.description}`);
             } else {
                 this.descriptionText.setText('Received empty description.');
             }
        }
    }

    private handleError(payload: any) {
        console.error('Received error from server:', payload.message || payload);
        this.descriptionText.setText(`Error: ${payload.message || 'Unknown server error'}`);
        this.stopPlayerMovement(); // Stop movement on error
    }

    private handleDialogue(payload: any) {
        console.log('Received dialogue:', payload);
        const speaker = payload.speaker || 'System';
        const line = payload.line || '';
        
        // Display dialogue in the description text area for now
        // TODO: Implement a proper dialogue box UI
        this.descriptionText.setText(`${speaker}: "${line}"`);

        // Stop player movement when dialogue starts
        this.stopPlayerMovement(); 
    }

    private parseAndSendCommand(text: string) {
        console.log(`Processing input: "${text}"`);
        this.descriptionText.setText(`> ${text}`); // Echo input
        this.stopPlayerMovement(); // Stop player on any command

        const words = text.toLowerCase().split(' ').filter(w => w); // Split, lowercase, remove empty
        const verb = words[0] || '';
        const noun = words.slice(1).join(' ') || ''; // Join remaining words

        // Handle client-side movement first
        if (['go', 'walk', 'move'].includes(verb)) {
             let targetX = this.player.x;
             let targetY = this.player.y;
             const moveAmount = 100; // Pixels to move
             switch(noun) {
                case 'north': case 'n': case 'up': targetY -= moveAmount; break;
                case 'south': case 's': case 'down': targetY += moveAmount; break;
                case 'east': case 'e': case 'right': targetX += moveAmount; break;
                case 'west': case 'w': case 'left': targetX -= moveAmount; break;
                default: 
                    this.descriptionText.setText("Go where? (Try north, south, east, west)"); 
                    return;
             }
             this.movePlayerTo(targetX, targetY);
 //            return; // Movement handled entirely client-side
        }

        // For all other commands, send the raw text to the backend
        if (text) {
            webSocketService.sendCommand('PROCESS_INPUT', { inputText: text });
        } else {
            // Handle empty input if needed, maybe do nothing or show a prompt
            this.descriptionText.setText(">");
        }
    }
} 