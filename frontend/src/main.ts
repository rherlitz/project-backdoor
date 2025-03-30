import Phaser from 'phaser';
import BootScene from './scenes/BootScene';
// Import other scenes here as they are created
import GameScene from './scenes/GameScene';

const config: Phaser.Types.Core.GameConfig = {
  type: Phaser.AUTO, // AUTO tries WebGL first, then Canvas
  width: 320,       // Base width - can be scaled
  height: 200,      // Base height - can be scaled
  parent: 'game-container', // Matches the div id in index.html
  pixelArt: true,     // Crucial for retro look - disables anti-aliasing
  physics: {        // Enable Arcade Physics
    default: 'arcade',
    arcade: {
      gravity: { x: 0, y: 0 }, // Set both x and y gravity
      debug: false // Set to true to see physics bodies/velocities
    }
  },
  scale: {
    mode: Phaser.Scale.FIT, // Fit the game within the available space while preserving aspect ratio
    autoCenter: Phaser.Scale.CENTER_BOTH // Center the game canvas horizontally and vertically
  },
  scene: [
    BootScene,
    // Add other scenes here
    GameScene
  ],
  render: {
    // Ensure crisp scaling
    pixelArt: true,
    antialias: false,
    antialiasGL: false,
  }
};

// Instantiate the game
const game = new Phaser.Game(config);

export default game; 