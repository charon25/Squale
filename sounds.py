import pygame

from sound_manager import SoundManager

BUTTON_CLICK = "buttonClick"
CELL_SELECT = "cellSelect"
REMOVE_CIRCLE = "validateCircleClick"
VALIDATE_CIRCLE_BLOCKER = "validateCircleBlocker"
VALIDATE_CIRCLE_CLICK = "validateCircleClick"
GROWING_CIRCLE = "growingCircle"
NO_CIRCLE_LEFT = "noCircleLeft"
DESTROY_CIRCLE = "destroyCircle"
START_LEVEL = "startLevel"
END_LEVEL = "endLevel"
BONUS_CIRCLE = "bonusCircle"
EOL_ANIM_CLICK = "eolAnimClick"
EOL_EARN_MEDAL = "eolEarnMedal"

MAX_MUSIC_VOLUME = 0.15


def add_sound(filepath: str, sound_name: str):
    SoundManager.instance().add_sound(filepath, sound_name)


def load_sounds():
    add_sound("resources/audio/sounds/btn_1.ogg", BUTTON_CLICK)

    add_sound("resources/audio/sounds/cell_select_1.wav", CELL_SELECT)

    add_sound("resources/audio/sounds/validate_circle_blocker_1.ogg", VALIDATE_CIRCLE_BLOCKER)

    add_sound("resources/audio/sounds/validate_circle_1.ogg", VALIDATE_CIRCLE_CLICK)

    add_sound("resources/audio/sounds/growing_circle.wav", GROWING_CIRCLE)

    add_sound("resources/audio/sounds/no_circles_1.ogg", NO_CIRCLE_LEFT)

    add_sound("resources/audio/sounds/destroy_circle_1.ogg", DESTROY_CIRCLE)

    add_sound("resources/audio/sounds/start_level_1.ogg", START_LEVEL)

    add_sound("resources/audio/sounds/end_level_1.ogg", END_LEVEL)

    add_sound("resources/audio/sounds/bonus_circle_1.ogg", BONUS_CIRCLE)

    add_sound("resources/audio/sounds/eol_anim_click_1.ogg", EOL_ANIM_CLICK)

    add_sound("resources/audio/sounds/earn_medal_1.ogg", EOL_EARN_MEDAL)


def start_music():
    pygame.mixer.music.load("resources/audio/music.mp3")
    pygame.mixer.music.play(loops=-1)
