import Phaser from 'phaser';
import { webSocketService } from '../services/WebSocketService';

export default class GameScene extends Phaser.Scene {
    private descriptionText!: Phaser.GameObjects.Text;
    private player!: Phaser.Types.Physics.Arcade.SpriteWithDynamicBody;
    private clippy!: Phaser.GameObjects.Sprite;
    private background!: Phaser.GameObjects.Image;
    private playerMoveTween: Phaser.Tweens.Tween | null = null;
    private parserInput!: HTMLInputElement;

    constructor() {
        super('GameScene');
    }

    preload() {
        console.log('GameScene: preload');
        // Load scene configuration
        this.load.json('sceneConfig', 'assets/data/scenes_config.json');

        // Load game assets here (backgrounds, sprites, etc.)
        this.load.image('bg_pod_interior', 'assets/images/backgrounds/pod_interior.png');
        this.load.image('bg_pod_exterior', 'assets/images/backgrounds/pod_exterior.png');
        this.load.image('bg_north_terrain', 'assets/images/backgrounds/north_terrain.png');
        this.load.image('bg_south_terrain', 'assets/images/backgrounds/south_terrain.png');
        this.load.image('bg_east_terrain', 'assets/images/backgrounds/east_terrain.png');
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
        this.background = this.add.image(this.cameras.main.centerX, this.cameras.main.centerY, 'bg_pod_interior');
        // Optional: Scale background to fit, maintain aspect ratio might be better depending on art
        const scaleX = this.cameras.main.width / this.background.width;
        const scaleY = this.cameras.main.height / this.background.height;
        const scale = Math.min(scaleX, scaleY);
        this.background.setScale(scale);
        this.background.setPosition(this.cameras.main.centerX, this.cameras.main.centerY);

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

        // Set world bounds and make it same as the scaled bg
        const scaledWidth = this.background.width * this.background.scaleX;
        const scaledHeight = this.background.height * this.background.scaleY;
        const bgTopLeftX = this.cameras.main.centerX - scaledWidth / 2;
        const bgTopLeftY = this.cameras.main.centerY - scaledHeight / 2;
        this.physics.world.setBounds(bgTopLeftX, bgTopLeftY, scaledWidth, scaledHeight);

        // --- Player Setup --- 
        // Initial player position (example - place near center bottom)
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
        webSocketService.on('scene_change', this.handleSceneChange, this);
        // Add more listeners for other message types from backend (e.g., 'npc_move')

        // Clean up listeners when the scene shuts down
        this.events.on(Phaser.Scenes.Events.SHUTDOWN, () => {
            console.log('GameScene: Shutting down, removing WS listeners');
            webSocketService.off('description', this.handleDescription, this);
            webSocketService.off('error', this.handleError, this);
            webSocketService.off('dialogue', this.handleDialogue, this);
            webSocketService.off('scene_change', this.handleSceneChange, this);
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

    private handleDescription(payload: { description: string }) {
        console.log('Received description:', payload);
        this.descriptionText.setText(payload.description);
    }

    private handleError(payload: { message: string }) {
        console.error('Received error:', payload);
        this.descriptionText.setText(`Error: ${payload.message}`);
        this.descriptionText.setColor('#ff0000');
        this.time.delayedCall(3000, () => { this.descriptionText.setColor('#ffffff'); });
    }

    private handleDialogue(payload: { speaker: string; line: string }) {
        console.log('Received dialogue:', payload);
        this.descriptionText.setText(`[${payload.speaker}]: ${payload.line}`);
    }

    private handleSceneChange(payload: { new_scene_id: string; new_description: string }) {
        console.log('Received scene_change:', payload);

        const config = this.cache.json.get('sceneConfig');
        if (!config) {
            console.error('Scene configuration not loaded!');
            this.handleError({ message: 'Internal error: Scene config missing.' });
            return;
        }

        const sceneData = config[payload.new_scene_id];
        if (!sceneData) {
            console.error(`Scene ID '${payload.new_scene_id}' not found in configuration!`);
            this.handleError({ message: `Internal error: Unknown scene ID '${payload.new_scene_id}'.` });
            return;
        }

        const backgroundKey = sceneData.background;
        if (!backgroundKey) {
            console.error(`Background key missing for scene ID '${payload.new_scene_id}' in configuration!`);
            this.handleError({ message: `Internal error: Missing background for '${payload.new_scene_id}'.` });
            return;
        }

        // Update background
        console.log(`Changing background to: ${backgroundKey}`);
        this.background.setTexture(backgroundKey);

        // Recalculate scale and reposition background
        const scaleX = this.cameras.main.width / this.background.width;
        const scaleY = this.cameras.main.height / this.background.height;
        const scale = Math.min(scaleX, scaleY);
        this.background.setScale(scale);
        this.background.setPosition(this.cameras.main.centerX, this.cameras.main.centerY);

        // Update world bounds to match new background
        const scaledWidth = this.background.width * this.background.scaleX;
        const scaledHeight = this.background.height * this.background.scaleY;
        const bgTopLeftX = this.cameras.main.centerX - scaledWidth / 2;
        const bgTopLeftY = this.cameras.main.centerY - scaledHeight / 2;
        this.physics.world.setBounds(bgTopLeftX, bgTopLeftY, scaledWidth, scaledHeight);

        // Update description text
        this.descriptionText.setText(payload.new_description);

        // TODO: Reposition player/NPCs based on new scene
        // For now, just place player roughly in center
        this.player.setPosition(this.cameras.main.centerX, this.cameras.main.centerY + scaledHeight * 0.3);
        this.stopPlayerMovement(); // Stop any lingering movement from old scene
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