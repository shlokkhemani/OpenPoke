/**
 * Notification sound utility using Web Audio API
 * Generates pleasant notification sounds without requiring external audio files
 */

export interface NotificationSoundSettings {
  enabled: boolean;
  volume: number; // 0.0 to 1.0
}

class NotificationSoundManager {
  private audioContext: AudioContext | null = null;
  private settings: NotificationSoundSettings = { enabled: true, volume: 0.7 };

  constructor() {
    // Initialize audio context on first user interaction
    this.initializeAudioContext();
  }

  private initializeAudioContext() {
    if (typeof window === 'undefined') return;
    
    // Create audio context on first user interaction
    const initAudio = () => {
      if (!this.audioContext) {
        try {
          this.audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
        } catch (error) {
          console.warn('Web Audio API not supported:', error);
        }
      }
    };

    // Initialize on any user interaction
    const events = ['click', 'touchstart', 'keydown'];
    const initOnce = () => {
      initAudio();
      events.forEach(event => document.removeEventListener(event, initOnce));
    };
    
    events.forEach(event => document.addEventListener(event, initOnce, { once: true }));
  }

  updateSettings(settings: NotificationSoundSettings) {
    this.settings = { ...settings };
  }

  async playNotificationSound(): Promise<void> {
    if (!this.settings.enabled || this.settings.volume === 0) return;
    if (!this.audioContext) {
      this.initializeAudioContext();
      if (!this.audioContext) return;
    }

    try {
      // Resume audio context if suspended (required by some browsers)
      if (this.audioContext.state === 'suspended') {
        await this.audioContext.resume();
      }

      // Play chime sound
      await this.playChimeSound();

    } catch (error) {
      console.warn('Failed to play notification sound:', error);
    }
  }

  // Pleasant chime sound
  private async playChimeSound(): Promise<void> {
    const now = this.audioContext!.currentTime;
    const duration = 0.4;

    // Create a pleasant chime with multiple harmonics
    const frequencies = [523.25, 659.25, 783.99]; // C5, E5, G5 chord
    
    frequencies.forEach((freq, index) => {
      const oscillator = this.audioContext!.createOscillator();
      const gain = this.audioContext!.createGain();
      
      oscillator.type = 'sine';
      oscillator.frequency.setValueAtTime(freq, now);
      
      const delay = index * 0.05; // Stagger the notes slightly
      gain.gain.setValueAtTime(0, now + delay);
      gain.gain.linearRampToValueAtTime(this.settings.volume * 0.3, now + delay + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.001, now + duration);
      
      oscillator.connect(gain);
      gain.connect(this.audioContext!.destination);
      
      oscillator.start(now + delay);
      oscillator.stop(now + duration);
    });
  }

  // Test sound for settings preview
  async playTestSound(): Promise<void> {
    await this.playNotificationSound();
  }
}

// Create singleton instance
export const notificationSound = new NotificationSoundManager();

// Export utility functions
export const playNotificationSound = () => notificationSound.playNotificationSound();
export const playTestSound = () => notificationSound.playTestSound();
export const updateNotificationSettings = (settings: NotificationSoundSettings) => 
  notificationSound.updateSettings(settings);
