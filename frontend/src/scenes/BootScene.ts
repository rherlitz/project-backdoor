import Phaser from 'phaser';
import { webSocketService } from '../services/WebSocketService'; // Import the singleton service

export default class BootScene extends Phaser.Scene {
  private statusText!: Phaser.GameObjects.Text;

  constructor() {
    super('BootScene');
  }

  preload() {
    // Load minimal assets needed for the loading screen or next scene
    // e.g., loading bar graphics, company logo
    console.log('BootScene: preload');
    // this.load.image('logo', 'assets/images/logo.png');
  }

  create() {
    console.log('BootScene: create');
    // pixelArt: true in game config handles default filtering
    // this.textures.setFilter(Phaser.Textures.FilterMode.NEAREST); // Incorrect line removed

    // Optionally, display a logo or loading message here

    // Start the next scene (e.g., a PreloadScene or the first game scene)
    // this.scene.start('PreloadScene');
    // For now, let's just add some placeholder text
    this.statusText = this.add.text(this.cameras.main.centerX, this.cameras.main.centerY, 'Initializing...', {
        font: '16px Arial',
        color: '#ffffff'
    }).setOrigin(0.5);

    // --- Connect to WebSocket --- 
    this.statusText.setText('Connecting to server...');
    webSocketService.connect()
        .then(() => {
            console.log('Initial connection successful in BootScene.');
            this.statusText.setText('Connected! Loading game...');
            // Proceed to the GameScene
            this.scene.start('GameScene'); 
        })
        .catch((error) => {
            console.error('Initial connection failed in BootScene:', error);
            this.statusText.setText('Connection Failed! Check server and console.');
            // Handle failure - maybe show a retry button or stop loading
        });
    
    // Optional: Listen for disconnection events globally if needed later
    webSocketService.on('disconnected', () => {
         console.warn('WebSocket disconnected (detected in BootScene listener)');
         // Might want to show an overlay or pause the game in other scenes
         // For BootScene, we might just update the status if still here
         if(this.scene.isActive('BootScene')) {
             this.statusText.setText('Connection Lost!');
         }
    });
  }
} 