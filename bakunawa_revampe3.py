import pygame
import random
import copy
import json
import unicodedata
import sys
import os
import math

# Initialization
pygame.init()
pygame.key.start_text_input()

# Constants
WIDTH, HEIGHT = 1200, 700
FPS = 60
LIVES_START = 7
WIKA = ["Cebuano", "Ilocano", "Filipino", "Hiligaynon", "Tagalog"]

# Base path for assets
# Adjust this path based on your device's file structure.
# For Android, it's often '/storage/emulated/0' or a subfolder within it.
# For desktop, it's typically a relative path like './Bakunawa Assets'.
BASE_ASSET_PATH = '/storage/emulated/0'

def get_asset_path(relative_path):
    """Helper to construct full asset paths."""
    # Ensure relative_path doesn't start with a slash if BASE_ASSET_PATH already ends with one
    if relative_path.startswith('/'):
        relative_path = relative_path.lstrip('/')
    return os.path.join(BASE_ASSET_PATH, relative_path)

def remove_accents(text):
    """Removes diacritic marks from characters (e.g., é -> e)."""
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )

# Load and categorize words
try:
    word_list_path = get_asset_path('Bakunawa Assets/Words/clean_cebuano_word_list.json')
    if not os.path.exists(word_list_path):
        print(f"Error: Word list file not found at {word_list_path}")
        cebuano_words = []
    else:
        with open(word_list_path, 'r', encoding='utf-8') as mga_salita:
            cebuano_words = json.load(mga_salita)
except Exception as e:
    print(f"Error loading word list: {e}")
    cebuano_words = []

madali_words = []
katamtaman_words = []
mahirap_words = []
for word in cebuano_words:
    wl = len(word)
    if 4 <= wl <= 6:
        madali_words.append(word)
    elif 7 <= wl <= 12:
        katamtaman_words.append(word)
    elif 13 <= wl <= 18:
        mahirap_words.append(word)

PALETTE = {
    "teal1": (33, 140, 144),
    "soft_yellow": (215, 181, 70),
    "soft_red": (180, 60, 60),
}

class Bulalakaw(pygame.sprite.Sprite):
    """Represents the falling meteorite/bulalakaw."""
    def __init__(self, pos_x, pos_y, asset_paths):
        super().__init__()
        self.sprites = []
        self.booming = False
        # Load falling animation frames
        for i in range(1, 7):
            img = pygame.image.load(get_asset_path(asset_paths['falling'].format(i))).convert_alpha()
            self.sprites.append(img)
        # Load boom animation frames
        for i in range(1, 7):
            img = pygame.image.load(get_asset_path(asset_paths['boom'].format(i))).convert_alpha()
            self.sprites.append(img)

        self.current_sprite = 0
        self.image = self.sprites[self.current_sprite]
        self.rect = self.image.get_rect(topleft=(pos_x, pos_y))
        self.animation_speed = 10.0
        self.animation_timer = 0.0

    def boom(self):
        """Starts the boom animation."""
        self.booming = True
        self.current_sprite = 6 # Start at the first boom frame (index 6)
        self.animation_timer = 0

    def update(self, delta_time):
        """Updates the bulalakaw's animation. Returns True if boom animation completes."""
        self.animation_timer += self.animation_speed * delta_time
        if not self.booming:
            if self.animation_timer >= 6: # Loop falling animation frames
                self.animation_timer = 0
            self.current_sprite = int(self.animation_timer) % 6
        else:
            # Boom animation has 6 frames (index 6 to 11)
            # Ensure the current_sprite does not exceed the last boom frame (11)
            target_sprite_index = 6 + int(self.animation_timer)
            if target_sprite_index >= 12: # Check if it has completed all boom frames (0-5 + 6 boom frames = 11 last index)
                self.current_sprite = 11 # Cap at the last frame
                return True # Indicate that booming is complete
            else:
                self.current_sprite = target_sprite_index

        self.image = self.sprites[self.current_sprite]
        return False # Indicate that booming is not yet complete or not booming

class SoundWaveProjectile:
    """Represents a sound wave projectile (hollow circle) that travels and fluctuates."""
    def __init__(self, xpos, ypos, target_x, target_y, speed=25, base_radius=30, thickness=4, color=(255, 255, 255)):
        self.x = float(xpos) # Use floats for smoother movement
        self.y = float(ypos)
        self.target_x = target_x
        self.target_y = target_y
        self.speed = speed # Speed at which the projectile travels (pixels per second, since scaled by delta_time)
        self.base_radius = base_radius # Core size of the hollow circle
        self.thickness = thickness # Thickness of the circle line
        self.color = color
        
        # Calculate direction vector for movement
        self.dx = self.target_x - self.x
        self.dy = self.target_y - self.y
        dist = (self.dx**2 + self.dy**2)**0.5
        if dist != 0:
            self.dx /= dist # Normalize
            self.dy /= dist # Normalize
        else: # Handle case where start and target are identical
            self.dx, self.dy = 0, -1 # Move straight up if no distinction
        
        self.done = False # Marks when the projectile should be removed

        # For fluctuation animation
        self.animation_timer = 0.0
        self.animation_speed = 30.0 # How fast the fluctuation cycles
        self.fluctuation_magnitude = 5 # How much the radius fluctuates (+/- pixels)

        # Initialize rect for collision, centered at current position
        self.current_radius = self.base_radius
        self.rect = pygame.Rect(0, 0, self.current_radius * 2, self.current_radius * 2)
        self.rect.center = (int(self.x), int(self.y))


    def update(self, delta_time):
        """Updates the projectile's position and fluctuation animation."""
        # Update position
        self.x += self.dx * self.speed * delta_time # Scale speed by delta_time for frame-rate independence
        self.y += self.dy * self.speed * delta_time

        # Update fluctuation animation
        self.animation_timer += self.animation_speed * delta_time
        # Use a sine wave for smooth fluctuation of the radius
        # The radius will oscillate between (base_radius - magnitude) and (base_radius + magnitude)
        self.current_radius = self.base_radius + self.fluctuation_magnitude * math.sin(self.animation_timer)
        self.current_radius = max(self.thickness, int(self.current_radius)) # Ensure radius is at least thickness
        
        # Update rect for movement and collision detection
        # Re-create rect with new fluctuating size, keeping center
        old_center = self.rect.center
        self.rect.width = self.rect.height = self.current_radius * 2
        self.rect.center = old_center # Keep it centered while resizing
        self.rect.center = (int(self.x), int(self.y)) # Then move it to current position

        # Mark as done if it goes off screen or significantly past the target
        
        # Check if projectile has passed the target point
        target_reached_x = (self.dx > 0 and self.x >= self.target_x) or \
                           (self.dx < 0 and self.x <= self.target_x) or \
                           self.dx == 0
        
        target_reached_y = (self.dy > 0 and self.y >= self.target_y) or \
                           (self.dy < 0 and self.y <= self.target_y) or \
                           self.dy == 0
        
        # If both x and y target are reached, or it's completely off screen, mark as done
        if (target_reached_x and target_reached_y) or not pygame.display.get_surface().get_rect().colliderect(self.rect):
            self.done = True


    def draw(self, surface):
        """Draws the hollow fluctuating circle."""
        if self.done or self.current_radius <= 0:
            return

        # Draw the circle directly on the main surface
        draw_color = self.color 
        
        try:
            # Draw on the surface using integer coordinates
            pygame.draw.circle(surface, draw_color, 
                               (int(self.x), int(self.y)), 
                               int(self.current_radius), 
                               self.thickness)
        except ValueError as e:
            # Handle cases where radius or color might temporarily be invalid
            pass # Just skip drawing this frame if invalid

class Word:
    """Represents a word falling from the top, attached to a Bulalakaw."""
    def __init__(self, text, speed, xpos, ypos, fonts, bulalakaw_asset_paths):
        self.text = text
        self.speed = speed
        self.typed = False # True when the word is successfully typed
        self.hit_by_projectile = False # True when hit by a projectile
        self.boom_animation_finished = False # Flag to track if the boom animation is done
        self.fonts = fonts

        self.bulalakaw = Bulalakaw(xpos, ypos, bulalakaw_asset_paths)
        self.rect = self.bulalakaw.rect.copy() # Word's rect follows bulalakaw's rect

        # Calculate text position relative to bulalakaw image
        text_surface = self.fonts['word'].render(self.text.upper(), True, pygame.Color('white'))
        self.text_offset_x = (self.rect.width - text_surface.get_width()) // 2
        self.text_offset_y = (self.rect.height - text_surface.get_height()) // 2 + 20

    def draw(self, surface, active_string):
        """Draws the bulalakaw and the word text."""
        surface.blit(self.bulalakaw.image, self.bulalakaw.rect)

        # Highlight typed prefix
        normalized_word = remove_accents(self.text.lower())
        normalized_input = remove_accents(active_string.lower())

        match_prefix = normalized_word.startswith(normalized_input) if normalized_input else False

        x = self.bulalakaw.rect.x + self.text_offset_x
        y = self.bulalakaw.rect.y + self.text_offset_y

        for i, char in enumerate(self.text.upper()):
            color = pygame.Color('green') if match_prefix and i < len(active_string) else pygame.Color('white')
            char_surface = self.fonts['word'].render(char, True, color)
            surface.blit(char_surface, (x, y))
            x += char_surface.get_width()

    def update(self, delta_time):
        """Updates the word's state and position. Returns True if word is ready for removal."""
        # A word only moves if it hasn't started booming
        if not self.bulalakaw.booming:
            self.bulalakaw.rect.y += self.speed
            self.rect = self.bulalakaw.rect.copy() # Keep word's rect synced

        # Update Bulalakaw animation. The Bulalakaw's update returns True when its *boom* animation is finished.
        if self.bulalakaw.update(delta_time):
            # If the bulalakaw was booming and its update returned True, it means its boom animation is finished.
            if self.bulalakaw.booming:
                self.boom_animation_finished = True
        
        # A word is ready for removal ONLY if it was hit by a projectile AND its boom animation is finished.
        # OR if it was NOT hit by a projectile and went off-screen (missed).
        if (self.hit_by_projectile and self.boom_animation_finished) or \
           (not self.typed and self.get_bottom() > HEIGHT): # Missed words are also removed
            return True # Mark for removal

        return False # Not yet ready for removal

    def trigger_typed(self):
        """Marks the word as typed. It continues its downward movement."""
        self.typed = True
        # Meteor will continue to fall, but is now "targetable" by projectile.

    def trigger_boom_from_hit(self):
        """Triggers the boom animation for the bulalakaw."""
        # Only boom if not already hit (to prevent double-booming)
        if not self.hit_by_projectile:
            self.hit_by_projectile = True
            self.bulalakaw.boom()

    def get_bottom(self):
        """Returns the bottom y-coordinate of the bulalakaw."""
        return self.bulalakaw.rect.bottom

class Button:
    """A generic button class for clickable elements."""
    def __init__(self, xpos, ypos, text, font, surface):
        self.xpos = xpos
        self.ypos = ypos
        self.text = text
        self.clicked = False
        self.font = font
        self.surface = surface
        self.rect = None

    def draw_circle_button(self, mouse_pos, mouse_clicked):
        """Draws a circular button."""
        self.clicked = False # Reset clicked state for the current frame
        circle = pygame.draw.circle(self.surface, (45, 89, 135), (self.xpos, self.ypos), 35)
        if circle.collidepoint(mouse_pos):
            if mouse_clicked:
                pygame.draw.circle(self.surface, (190, 35, 35), (self.xpos, self.ypos), 35)
                self.clicked = True
            else:
                pygame.draw.circle(self.surface, (190, 89, 135), (self.xpos, self.ypos), 35)
        pygame.draw.circle(self.surface, pygame.Color('white'), (self.xpos, self.ypos), 35, 3)
        text_surface = self.font.render(self.text, True, pygame.Color('white'))
        self.surface.blit(text_surface, (self.xpos - text_surface.get_width() // 2, self.ypos - text_surface.get_height() // 2))
        self.rect = circle
        return self.clicked

    def draw_rect_button(self, mouse_pos, mouse_clicked):
        """Draws a rectangular button."""
        self.clicked = False # Reset clicked state for the current frame
        rect = pygame.Rect(self.xpos, self.ypos, 400, 70)
        pygame.draw.rect(self.surface, PALETTE["soft_yellow"], rect, border_radius=6)
        if rect.collidepoint(mouse_pos):
            if mouse_clicked:
                pygame.draw.rect(self.surface, (190, 35, 35), rect, border_radius=3)
                self.clicked = True
            else:
                pygame.draw.rect(self.surface, (190, 89, 135), rect, border_radius=3)
        pygame.draw.rect(self.surface, pygame.Color('white'), rect, 2, border_radius=6)
        text_surface = self.font.render(self.text, True, pygame.Color('white'))
        text_pos = (self.xpos + (400 - text_surface.get_width()) // 2, self.ypos + (70 - text_surface.get_height()) // 2)
        self.surface.blit(text_surface, text_pos)
        self.rect = rect
        return self.clicked

class Image:
    """Simple class to draw a scaled image."""
    def __init__(self, img, width, height, xpos, ypos):
        self.image = pygame.transform.scale(img, (width, height))
        self.xpos = xpos
        self.ypos = ypos

    def draw(self, surface):
        """Draws the image on the given surface."""
        surface.blit(self.image, (self.xpos, self.ypos))

class LivesIndicator:
    """
    Displays remaining lives as moon images in sequence.
    Images are ordered from full lives (index 0) to game over (last index).
    """
    def __init__(self, image_paths, xpos, ypos, width, height, max_lives=7):
        self.images = []
        for path in image_paths:
            img = pygame.image.load(get_asset_path(path)).convert_alpha()
            img = pygame.transform.scale(img, (width, height))
            self.images.append(img)
        self.xpos = xpos
        self.ypos = ypos
        self.max_lives = max_lives

    def draw(self, surface, lives_remaining):
        """Draws the moon image corresponding to remaining lives."""
        index = self.max_lives - lives_remaining
        index = max(0, min(index, len(self.images) - 1))
        surface.blit(self.images[index], (self.xpos, self.ypos))

class Game:
    """Main game class managing game state, assets, and loop."""
    def __init__(self, madali_words, katamtaman_words, mahirap_words):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Bakunawa: Typing Game")
        self.clock = pygame.time.Clock()
        
        self.game_over = False

        self.madali_words = madali_words
        self.katamtaman_words = katamtaman_words
        self.mahirap_words = mahirap_words

        self.assets = self.load_assets()
        self.bg = Image(self.assets['bg_img'], WIDTH, HEIGHT, 0, 0)
        self.fonts = self.assets['fonts']
        # Load the gong sound effect
        self.gong_sfx = self.assets['gong_sfx']

        self.lives = LIVES_START
        self.level = 1
        self.score = 0
        self.active_string = ''
        self.submit = ''
        self.paused = False
        self.new_level = True # Flag to indicate if a new level needs to be generated
        self.word_objects = []
        self.words_generated_this_level = 0
        self.words_typed_this_level = 0
        self.words_missed_this_level = 0

        # Actor animation state
        self.actor_current_frame = 0
        self.actor_animation_timer = 0.0
        self.actor_is_animating = False
        self.actor_animation_speed = 10.0
        self.actor_animation_duration_frames = len(self.abatang_frames)

        # Initial actor image is the idle one
        self.actor_idle_image = pygame.image.load(get_asset_path('Bakunawa Assets/Pictures/Sprites/Tao/abatang1.png')).convert_alpha()
        self.actor_idle_image = pygame.transform.scale(self.actor_idle_image, (160, 160))
        self.current_actor_image = self.actor_idle_image # Set initial image here
        self.actor_pos_x = 69
        self.actor_pos_y = 509

        # New: Store the target word for projectile generation after actor animation
        self.projectile_pending_target = None 

        moon_lives_paths = [
            'Bakunawa Assets/Pictures/Sprites/Moon/Buwan_1.png',
            'Bakunawa Assets/Pictures/Sprites/Moon/Buwan_2.png',
            'Bakunawa Assets/Pictures/Sprites/Moon/Buwan_3.png',
            'Bakunawa Assets/Pictures/Sprites/Moon/Buwan_4.png',
            'Bakunawa Assets/Pictures/Sprites/Moon/Buwan_5.png',
            'Bakunawa Assets/Pictures/Sprites/Moon/Buwan_6.png',
            'Bakunawa Assets/Pictures/Sprites/Moon/Buwan_7.png',
            'Bakunawa Assets/Pictures/Sprites/Moon/Buwan_8.png'  # Game over image
        ]

        self.lives_indicator = LivesIndicator(
            image_paths=moon_lives_paths,
            xpos=819,
            ypos=540,
            width=160,
            height=160,
            max_lives=7
        )

        self.bulalakaw_assets = {
            "falling": 'Bakunawa Assets/Pictures/Sprites/Bulalakaw/Falling/Bulalakaw_{}.png',
            "boom": 'Bakunawa Assets/Pictures/Sprites/Bulalakaw/Boom/Sabog_{}.png'
        }
        
        # Projectile setup (now SoundWaveProjectile)
        self.projectiles = [] # List to hold active projectile objects (SoundWaveProjectile instances)

        # Difficulty choices
        self.choices = [True, False, False] # [Madali, Katamtaman, Mahirap]
        self.last_choices_before_pause = copy.deepcopy(self.choices)

    def load_assets(self):
        """Loads all game assets (images, fonts, sounds)."""
        assets = {}
        assets['bg_img'] = pygame.image.load(get_asset_path('Download/bakunawa_landscape.png')).convert()
        
        # Load Abatang (Gong Banging) animation frames
        self.abatang_frames = []
        for i in range(1, 5):
            path = get_asset_path(f'Bakunawa Assets/Pictures/Sprites/Tao/abatang{i}.png')
            try:
                img = pygame.image.load(path).convert_alpha()
                img = pygame.transform.scale(img, (160, 160))
                self.abatang_frames.append(img)
            except pygame.error as e:
                print(f"Warning: Could not load abatang frame {path}: {e}")
                if not self.abatang_frames: # If first frame fails, use a generic fallback
                    placeholder_path = get_asset_path('Bakunawa Assets/Pictures/Sprites/Tao/abatang1.png')
                    try:
                        placeholder_img = pygame.image.load(placeholder_path).convert_alpha()
                        placeholder_img = pygame.transform.scale(placeholder_img, (160, 160))
                        self.abatang_frames.append(placeholder_img)
                    except pygame.error as ee:
                        print(f"CRITICAL ERROR: Could not load even the fallback actor image: {ee}")
                        self.abatang_frames.append(pygame.Surface((160,160), pygame.SRCALPHA)) # Blank surface
                        self.abatang_frames[0].fill((0,0,0,255))
                else: # If later frames fail, just duplicate the last successful frame
                    self.abatang_frames.append(self.abatang_frames[-1])

        assets['moon_tanga'] = pygame.image.load(get_asset_path('Bakunawa Assets/Pictures/Sprites/Moon/moontanga.png')).convert_alpha()

        assets['fonts'] = {
            'karatula': pygame.font.Font(get_asset_path('Bakunawa Assets/Fonts/LL KARATULA 020721.ttf'), 30),
            'karatula_65': pygame.font.Font(get_asset_path('Bakunawa Assets/Fonts/LL KARATULA 020721.ttf'), 65),
            'karatula_25': pygame.font.Font(get_asset_path('Bakunawa Assets/Fonts/LL KARATULA 020721.ttf'), 25),
            'karatula_45': pygame.font.Font(get_asset_path('Bakunawa Assets/Fonts/LL KARATULA 020721.ttf'), 45),
            'square': pygame.font.Font(get_asset_path('Bakunawa Assets/Fonts/Square.ttf'), 50),
            'kawit': pygame.font.Font(get_asset_path('Bakunawa Assets/Fonts/KawitFree-CndItalic.ttf'), 85),
            'martiresExtraBold': pygame.font.Font(get_asset_path('Bakunawa Assets/Fonts/BBTMartiresFree-ExtraBold.ttf'), 55),
            'pause': pygame.font.Font(get_asset_path('Bakunawa Assets/Fonts/1up.ttf'), 38),
            'word': pygame.font.Font(get_asset_path('Bakunawa Assets/Fonts/GentiumPlus-Bold.ttf'), 38)
        }

        # Load sound effects
        try:
            assets['gong_sfx'] = pygame.mixer.Sound(get_asset_path('Bakunawa Assets/Sounds/Sfx/sfx_gong.wav'))
        except pygame.error as e:
            print(f"Warning: Could not load gong sound effect: {e}")
            assets['gong_sfx'] = None # Set to None if loading fails

        return assets

    def generate_level(self):
        """Generates words for the current level based on chosen difficulty."""
        word_objs = []
        if self.choices[0]: # Madali
            wordlist = self.madali_words
        elif self.choices[1]: # Katamtaman
            wordlist = self.katamtaman_words
        elif self.choices[2]: # Mahirap
            wordlist = self.mahirap_words
        else: # Default to Madali if no choice is made
            wordlist = self.madali_words

        if not wordlist:
            print("Warning: Selected word list is empty. Cannot generate words.")
            return []

        sample_img = pygame.image.load(get_asset_path(self.bulalakaw_assets['falling'].format(1))).convert_alpha()
        meteorite_w, meteorite_h = sample_img.get_size()

        occupied_x = [] # To store x-ranges of placed words for collision detection
        words_needed = self.level
        attempts = 0
        max_attempts = 1000

        while len(word_objs) < words_needed and attempts < max_attempts:
            text = random.choice(wordlist).lower()
            text_surface = self.fonts['word'].render(text.upper(), True, (255, 255, 255))
            text_w = text_surface.get_width()

            left_pad = 50
            right_pad = 50
            min_spacing = 60 # Minimum horizontal spacing between meteorites
            max_x = WIDTH - meteorite_w - right_pad

            if max_x < left_pad or text_w > meteorite_w - 10:
                attempts += 1
                continue

            found_x = False
            inner_attempts = 0
            max_inner = 50

            while not found_x and inner_attempts < max_inner:
                xpos = random.randint(left_pad, max_x)

                overlap = False
                for (start_x, end_x) in occupied_x:
                    new_left = xpos - min_spacing
                    new_right = xpos + meteorite_w + min_spacing
                    exist_left = start_x - min_spacing
                    exist_right = end_x + min_spacing
                    if not (new_right < exist_left or new_left > exist_right):
                        overlap = True
                        break

                if not overlap:
                    found_x = True
                inner_attempts += 1

            if found_x:
                ypos = -meteorite_h - random.randint(10, 50) # Start slightly off-screen
                speed = random.randint(4, 5) # Bulalakaw speed
                new_word = Word(text, speed, xpos, ypos, self.fonts, self.bulalakaw_assets)
                word_objs.append(new_word)
                occupied_x.append((xpos, xpos + meteorite_w))
                attempts = 0
            else:
                attempts += 1

        if len(word_objs) < words_needed:
            print(f"Warning: only generated {len(word_objs)} words for level {self.level}")

        self.words_generated_this_level = len(word_objs)
        self.words_typed_this_level = 0
        self.words_missed_this_level = 0

        return word_objs

    def check_answer(self):
        """Checks if the typed string matches any active word."""
        word_typed = None
        normalized_submit = remove_accents(self.submit.lower())
        for word in self.word_objects:
            if not word.typed: # Only consider words that haven't been typed yet
                normalized_word = remove_accents(word.text.lower())
                if normalized_word == normalized_submit:
                    word_typed = word
                    break

        if word_typed:
            # Calculate score based on word length and speed
            points = word_typed.speed * len(word_typed.text) * 10 * (len(word_typed.text) // 3)
            self.score += int(points)
            self.words_typed_this_level += 1
            word_typed.trigger_typed() # Mark as typed. Meteor continues falling.

            # Trigger actor animation for "shooting" (gong banging)
            self.actor_is_animating = True
            self.actor_current_frame = 0
            self.actor_animation_timer = 0.0
            
            # Instead of creating the projectile here, store the target word
            self.projectile_pending_target = word_typed
            
        self.submit = '' # Clear submitted string after checking

    def draw_screen(self, mouse_pos, mouse_clicked):
        """Draws the main game screen elements."""
        self.screen.fill((0, 0, 0))
        self.bg.draw(self.screen)
        
        self.lives_indicator.draw(self.screen, self.lives if self.lives >= 0 else 0)
        
        # Draw the dynamically updated actor image (idle or animating)
        self.screen.blit(self.current_actor_image, (self.actor_pos_x, self.actor_pos_y))
        
        # UI rectangles and borders
        pygame.draw.rect(self.screen, pygame.Color('white'), (250, 570, 550, 100), 1, border_radius=20)
        pygame.draw.rect(self.screen, pygame.Color('white'), (1000, 571, 170, 100), 1, border_radius=20)
        pygame.draw.rect(self.screen, pygame.Color('white'), (0, 0, WIDTH, HEIGHT), 3)
        pygame.draw.rect(self.screen, pygame.Color('black'), (0, 0, WIDTH, HEIGHT), 2)

        # Text elements
        self.screen.blit(self.fonts['karatula_65'].render(f'{self.lives}', True, pygame.Color("white")), (1060, 605))
        self.screen.blit(self.fonts['karatula_25'].render(f'Buwan:', True, pygame.Color("white")), (1020, 577))
        self.screen.blit(self.fonts['karatula'].render(f'Wika: {WIKA[3]}', True, pygame.Color('white')), (20, 20))
        self.screen.blit(self.fonts['karatula'].render(f'Antas: {self.level}', True, pygame.Color('white')), (20, 60))
        self.screen.blit(self.fonts['kawit'].render(self.active_string, True, pygame.Color('white')), (260, 582))
        self.screen.blit(self.fonts['karatula'].render(f'Puntos: {self.score}', True, pygame.Color('white')), (545, 35))

        # Pause button
        self.pause_button = Button(1130, 60, 'II', self.fonts['pause'], self.screen)
        # Returns True if clicked, False otherwise
        return self.pause_button.draw_circle_button(mouse_pos, mouse_clicked)

    def draw_game_over(self, mouse_pos, mouse_clicked):
        """Draws the game over screen."""
        face = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        face.fill((0, 0, 0, 120))
        pygame.draw.rect(face, (*PALETTE['soft_red'], 150), [250, 120, 700, 490], 0, 5)
        pygame.draw.rect(face, (0,0,0,200), [250, 120, 700, 490], 5, 5)
        pygame.draw.rect(face, (0,0,0,250), [250, 160, 700, 80], 0, 5)
        
        phrase_text = 'NAUBOS NA ANG IYONG BUWAN!'
        phrase_surface = self.fonts['karatula_45'].render(phrase_text, True, pygame.Color(178, 34, 34))
        phrase_pos = (WIDTH // 2 - phrase_surface.get_width() // 2, 180)
        face.blit(phrase_surface, phrase_pos)

        score_label = f'Puntos: {self.score}'
        score_surface = self.fonts['karatula_45'].render(score_label, True, pygame.Color('white'))
        score_pos = (WIDTH // 2 - score_surface.get_width() // 2, 280)
        face.blit(score_surface, score_pos)

        # Buttons
        continue_button = Button(450, 400, '>', self.fonts['pause'], face)
        exit_button = Button(450, 500, 'X', self.fonts['pause'], face)
        
        con = "Maglaro ulit"
        con_face = self.fonts['karatula_45'].render(con, True, pygame.Color('white'))
        face.blit(con_face, (500, 377))
        ex = 'Umalis'
        ex_face = self.fonts['karatula_45'].render(ex, True, pygame.Color('white'))
        face.blit(ex_face, (500, 477))

        clicked_continue = continue_button.draw_circle_button(mouse_pos, mouse_clicked)
        clicked_exit = exit_button.draw_circle_button(mouse_pos, mouse_clicked)

        self.screen.blit(face, (0, 0))

        return clicked_continue, clicked_exit

    def draw_pause(self, mouse_pos, mouse_clicked):
        """Draws the pause menu."""
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        pygame.draw.rect(overlay, (0,0,0,100), [250, 120, 700, 490], 0, 5)
        pygame.draw.rect(overlay, (0,0,0,200), [250, 120, 700, 490], 5, 5)

        overlay.blit(self.fonts['karatula_45'].render('TALAKSAN', True, pygame.Color('white')), (486, 123))
        overlay.blit(self.fonts['karatula_45'].render('ITULOY', True, pygame.Color('white')), (354, 207))
        overlay.blit(self.fonts['karatula_45'].render('UMALIS', True, pygame.Color('white')), (754, 207))
        overlay.blit(self.fonts['karatula_45'].render('ANTAS', True, pygame.Color('white')), (538, 300))

        self.resume_button = Button(305, 230, '>', self.fonts['pause'], overlay)
        self.quit_button = Button(705, 230, 'X', self.fonts['pause'], overlay)
        
        resume_clicked = self.resume_button.draw_circle_button(mouse_pos, mouse_clicked)
        quit_clicked = self.quit_button.draw_circle_button(mouse_pos, mouse_clicked)

        madali_button = Button(405, 349, 'MADALI', self.fonts['square'], overlay)
        katamtaman_button = Button(405, 435, 'KATAMTAMAN', self.fonts['square'], overlay)
        mahirap_button = Button(405, 520, 'MAHIRAP', self.fonts['square'], overlay)
        buttons = [madali_button, katamtaman_button, mahirap_button]

        for i, btn in enumerate(buttons):
            if btn.draw_rect_button(mouse_pos, mouse_clicked): # draw_rect_button now also returns clicked status
                for j in range(len(self.choices)):
                    self.choices[j] = (i == j)

        button_rects = [(405, 349, 400, 70), (405, 435, 400, 70), (405, 520, 400, 70)]
        for i, selected in enumerate(self.choices):
            if selected:
                x, y, w, h = button_rects[i]
                pygame.draw.rect(overlay, pygame.Color('green'), (x, y, w, h), 6, border_radius=6)

        self.screen.blit(overlay, (0, 0))
        return resume_clicked, self.choices, quit_clicked

    def main_loop(self):
        """The main game loop."""
        mouse_clicked_this_frame = False
        while True:
            delta_time = self.clock.tick(FPS) / 1000.0
            mouse_pos = pygame.mouse.get_pos()
            mouse_clicked_this_frame = False

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    sys.exit()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_clicked_this_frame = True
                
                # --- INPUT HANDLING BLOCK ---
                # These events should only be processed if the game is NOT paused and NOT game over
                if not self.paused and not self.game_over:
                    if event.type == pygame.TEXTINPUT:
                        self.active_string += event.text
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_BACKSPACE:
                            self.active_string = self.active_string[:-1]
                        elif event.key == pygame.K_RETURN:
                            self.submit = self.active_string.lower()
                            self.active_string = ''
                            self.check_answer() # Call check_answer immediately on RETURN
                
                # Handle ESCAPE key for pause/unpause, always allowed
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if self.paused:
                        self.paused = False
                        # Reset level if difficulty changed during pause
                        if self.choices != self.last_choices_before_pause:
                            self.level = 1
                            self.new_level = True
                            self.score = 0
                            self.lives = LIVES_START
                            self.word_objects = []
                            self.words_generated_this_level = 0
                            self.words_typed_this_level = 0
                            self.words_missed_this_level = 0
                        self.last_choices_before_pause = copy.deepcopy(self.choices)
                    else:
                        self.paused = True
                        self.last_choices_before_pause = copy.deepcopy(self.choices)

            # --- DRAWING AND GAME LOGIC ---
            # Draw the screen and get if the pause button was clicked
            pause_button_clicked = self.draw_screen(mouse_pos, mouse_clicked_this_frame)

            # Check if the pause button was clicked and the game is not already paused or over
            if pause_button_clicked and not self.paused and not self.game_over:
                self.paused = True
                self.last_choices_before_pause = copy.deepcopy(self.choices)

            if self.paused:
                resume_clicked, _, quit_clicked = self.draw_pause(mouse_pos, mouse_clicked_this_frame)
                if resume_clicked:
                    self.paused = False
                    if self.choices != self.last_choices_before_pause:
                        self.level = 1
                        self.new_level = True
                        self.score = 0
                        self.lives = LIVES_START
                        self.word_objects = []
                        self.words_generated_this_level = 0
                        self.words_typed_this_level = 0
                        self.words_missed_this_level = 0
                    self.last_choices_before_pause = copy.deepcopy(self.choices)
                if quit_clicked:
                    pygame.quit()
                    sys.exit()
            elif self.game_over:
                continue_clicked, exit_clicked = self.draw_game_over(mouse_pos, mouse_clicked_this_frame)
                if continue_clicked:
                    self.game_over = False
                    self.paused = True # Go to pause screen to select difficulty
                    self.lives = LIVES_START
                    self.score = 0
                    self.word_objects = []
                    self.level = 1
                    self.new_level = True
                    self.active_string = ''
                    self.submit = ''
                    self.words_generated_this_level = 0
                    self.words_typed_this_level = 0
                    self.words_missed_this_level = 0
                    self.last_choices_before_pause = copy.deepcopy(self.choices)
                if exit_clicked:
                    pygame.quit()
                    sys.exit()
            else: # Game is running
                if self.new_level:
                    self.word_objects = self.generate_level()
                    self.new_level = False

                # Update actor animation
                if self.actor_is_animating:
                    self.actor_animation_timer += self.actor_animation_speed * delta_time
                    
                    # Check if animation is completing this frame
                    if self.actor_animation_timer >= self.actor_animation_duration_frames:
                        # Play gong sound effect here
                        if self.gong_sfx:
                            self.gong_sfx.play()

                        self.actor_is_animating = False
                        self.actor_current_frame = 0
                        self.actor_animation_timer = 0.0
                        self.current_actor_image = self.actor_idle_image

                        # Launch projectile ONLY when animation is done and there's a pending target
                        if self.projectile_pending_target:
                            word_to_hit = self.projectile_pending_target
                            projectile_start_x = self.actor_pos_x + self.current_actor_image.get_width() // 2 + 30
                            projectile_start_y = self.actor_pos_y + self.current_actor_image.get_height() // 2 - 20
                            
                            projectile_target_x = word_to_hit.bulalakaw.rect.centerx
                            projectile_target_y = word_to_hit.bulalakaw.rect.centery
                            
                            new_projectile = SoundWaveProjectile(
                                projectile_start_x, 
                                projectile_start_y, 
                                projectile_target_x, 
                                projectile_target_y,
                                speed=1200, 
                                base_radius=20, 
                                thickness=4, 
                                color=(49, 149, 149) # You can change this color here
                            ) 
                            self.projectiles.append(new_projectile)
                            self.projectile_pending_target = None 
                    else:
                        self.actor_current_frame = int(self.actor_animation_timer)
                        self.actor_current_frame = min(self.actor_current_frame, self.actor_animation_duration_frames - 1)
                        self.current_actor_image = self.abatang_frames[self.actor_current_frame]

                # Update and draw words
                words_to_remove = []
                for word in self.word_objects:
                    word.draw(self.screen, self.active_string)
                    if word.update(delta_time): 
                        if not word.hit_by_projectile and word.get_bottom() > HEIGHT: 
                            self.lives -= 1
                            self.words_missed_this_level += 1
                        words_to_remove.append(word)

                for word in words_to_remove:
                    self.word_objects.remove(word)
                
                # Check for projectile-word collisions and update projectiles
                projectiles_to_remove = []
                for proj in self.projectiles:
                    proj.update(delta_time)
                    proj.draw(self.screen) 
                    
                    if proj.done: 
                        projectiles_to_remove.append(proj)
                        continue 

                    # Collision logic for SoundWaveProjectile:
                    # Check if the word's bulalakaw rect is *colliding* with the projectile's rect
                    # AND if the word is typed and not yet hit.
                    for word in self.word_objects:
                        if word.typed and not word.hit_by_projectile and proj.rect.colliderect(word.bulalakaw.rect):
                            word.trigger_boom_from_hit()
                            proj.done = True 
                            break 

                for proj in projectiles_to_remove:
                    if proj in self.projectiles:
                        self.projectiles.remove(proj)

                # Level completion logic
                if self.words_typed_this_level + self.words_missed_this_level >= self.words_generated_this_level and self.words_generated_this_level > 0:
                    if len(self.word_objects) == 0 and len(self.projectiles) == 0:
                        self.level += 1
                        self.new_level = True

                # Game over condition
                if self.lives <= 0:
                    self.game_over = True
                    self.lives = 0 

            pygame.display.flip()

if __name__ == '__main__':
    game = Game(madali_words, katamtaman_words, mahirap_words)
    game.main_loop()