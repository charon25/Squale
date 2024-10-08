import math
import random

import pygame as pyg

import constants as co
import sounds
import textures
import utils
from cell import Cell
from circle import Circle
from constants import CellType
from levels import LevelData, get_level
from sound_manager import SoundManager
from window import Scale


class LevelManager:
    INSTANCE = None

    def __init__(self):
        self.number = co.INITIAL_LEVEL - 1
        self.current_level: Level = None
        self.in_loading_anim = False
        self.current_level_ended = False
        self.all_level_complete = False

        self.gold_medals: dict[int, bool] = {n: False for n in range(co.LEVEL_COUNT)}

    @classmethod
    def instance(cls) -> 'LevelManager':
        if cls.INSTANCE is None:
            cls.INSTANCE = LevelManager()
        return cls.INSTANCE

    @classmethod
    def reset(cls):
        cls.INSTANCE = LevelManager()

    def load_next_level(self):
        self.load_level(self.number + 1)

    def load_previous_level(self):
        self.load_level(self.number - 1)

    def reload_current_level(self):
        self.load_level(self.number)

    def __get_level(self):
        level_data: LevelData = get_level(self.number)
        return Level(
            level_data.number,
            level_data.cell_size,
            level_data.max_circle_count,
            level_data.required_points,
            level_data.cells
        )

    def load_level(self, number: int):
        self.number = number
        self.current_level = self.__get_level()

        self.current_level_ended = False
        self.current_level.start_loading_animation()
        self.in_loading_anim = True

    def on_level_loaded(self):
        self.in_loading_anim = False

    def on_level_unloaded(self):
        self.current_level_ended = True
        self.gold_medals[self.number] = self.current_level.got_gold_medal()

    def on_last_level(self):
        return self.number == co.LEVEL_COUNT - 1


class Level:
    def __init__(self, number: int, cell_size: int, max_circles_count: int,
                 required_points: list[int],
                 cells: list[Cell]):
        self.number = number
        self.cell_size = cell_size
        self.cells = sorted(cells)
        self.hovered_cell: Cell | None = None

        self.x_offset, self.y_offset, self.width, self.height = 0, 0, 0, 0
        self.rect: pyg.Rect = None
        self.radius_inc_speed: float = 0.0
        self.terrain: list[list[Cell]] = None
        self.__compute_terrain()

        self.circles: list[ValidatedCircle] = list()
        self.temp_circle: Circle | None = None
        self.temp_selected_cells: list[Cell] = list()
        self.temp_multiplier: float = 1.0
        self.circumscribed_circle: Circle = Circle(self.width // 2, self.height // 2, 0)

        self.max_circles_count = max_circles_count
        self.max_circles_count_upgrade = 0
        self.current_circles_count = 0

        self.required_points = sorted(required_points)
        self.points: float = 0.0
        self.cells_in_animation = 0
        self.countdown: float = 0.0

        self.animation = 0  # 0 : pas d'anim, 1 : loading, -1 : unloading
        self.tutorials: list[str] = co.LEVEL_TUTORIALS[self.number] if self.number < len(co.LEVEL_TUTORIALS) else list()

    def __compute_terrain(self):
        min_x: int = co.WIDTH
        max_x: int = 0
        min_y: int = co.HEIGHT
        max_y: int = 0
        max_cx: int = 0
        max_cy: int = 0
        x_center, y_center = 0, 0
        max_cell_size = 0
        for k, cell in enumerate(self.cells):
            cell.generate(self.cell_size, k, self.on_cell_selected)
            min_x = min(min_x, cell.rect.left)
            max_x = max(max_x, cell.rect.right)
            min_y = min(min_y, cell.rect.top)
            max_y = max(max_y, cell.rect.bottom)
            max_cx = max(max_cx, cell.x + cell.size)
            max_cy = max(max_cy, cell.y + cell.size)
            x_center += cell.rect.centerx
            y_center += cell.rect.centery
            max_cell_size = max(max_cell_size, cell.real_size)

        self.x_offset = (co.WIDTH - (max_x - min_x)) / 2 - min_x
        self.y_offset = co.GAME_Y_OFFSET + (co.HEIGHT - co.GAME_Y_OFFSET - (max_y - min_y)) / 2 - min_y
        self.width = max_x - min_x
        self.height = max_y - min_y
        self.rect = pyg.Rect(self.x_offset, self.y_offset, self.width, self.height)
        self.radius_inc_speed = 1.5 * max(64, max_cell_size)

        self.terrain: list[list[Cell]] = [[None for _ in range(max_cx)] for __ in range(max_cy)]
        for cell in self.cells:
            for cx in range(cell.x, cell.x + cell.size):
                for cy in range(cell.y, cell.y + cell.size):
                    self.terrain[cy][cx] = cell

        x_center = x_center / len(self.cells)
        y_center = y_center / len(self.cells)

        for cell in self.cells:
            mag = math.dist(cell.rect.center, (x_center, y_center))
            if mag == 0:
                angle = random.random() * 2 * math.pi
                cell.vector = (math.cos(angle), math.sin(angle))
            else:
                cell.vector = ((cell.rect.centerx - x_center) / mag, (cell.rect.centery - y_center) / mag)

    def reset(self):
        self.temp_selected_cells = list()
        for cell in self.cells:
            cell.unselect()

        self.circles = list()
        self.temp_circle = None
        self.temp_multiplier = 1.0
        self.circumscribed_circle = Circle(self.width // 2, self.height // 2, 0)

        self.max_circles_count_upgrade = 0
        self.current_circles_count = 0

        self.points = 0.0

        self.cells_in_animation = 0
        self.countdown = 0.0

    def _flood_fill(self, x0: int, y0: int) -> list[Cell]:
        stack: list[tuple[int, int]] = list()
        visited: set[tuple[int, int]] = set()
        cells: list[Cell] = list()
        stack.append((x0, y0))
        while stack:
            x, y = stack.pop()
            if not (x, y) in visited:
                cells.append(self.terrain[y][x])
                visited.add((x, y))
                if x > 0 and self.terrain[y][x - 1] is not None:
                    stack.append((x - 1, y))
                if x < len(self.terrain[0]) - 1 and self.terrain[y][x + 1] is not None:
                    stack.append((x + 1, y))
                if y > 0 and self.terrain[y - 1][x] is not None:
                    stack.append((x, y - 1))
                if y < len(self.terrain) - 1 and self.terrain[y + 1][x] is not None:
                    stack.append((x, y + 1))

        return cells

    # region ===== CERCLE =====

    def click_on_level(self, x: int, y: int):
        if self.animation != 0:
            return

        x = x - self.x_offset
        y = y - self.y_offset

        for v_circle in self.circles:
            if v_circle.circle.contains_point(x, y):
                self.remove_circle(v_circle)
                return

        if self.current_circles_count >= self.max_circles_count + self.max_circles_count_upgrade:
            SoundManager.instance().play_sound(sounds.NO_CIRCLE_LEFT, volume=0.7)
            return

        if not any(cell.contains_point(x, y) for cell in self.cells):
            SoundManager.instance().play_sound(sounds.NO_CIRCLE_LEFT, volume=0.2)
            return

        self.temp_circle = Circle(x, y, 0)
        self.temp_multiplier = 1.0
        SoundManager.instance().play_sound(sounds.GROWING_CIRCLE, volume=0.4)

    def validate_temp_circle(self, sound: str = sounds.VALIDATE_CIRCLE_CLICK):
        if self.temp_circle is None:
            return

        if self.temp_circle.radius < self.cell_size * 0.4:
            self.destroy_temp_circle()
            return

        self.temp_selected_cells = sorted(self.temp_selected_cells)

        self.cells_in_animation += len(self.temp_selected_cells)

        points = 0
        for k, cell in enumerate(self.temp_selected_cells):
            cell.select(len(self.temp_selected_cells), k)
            cell.points += cell.get_points() * self.temp_multiplier

            points += cell.get_points()

        self.circles.append(ValidatedCircle(self.temp_circle, self.temp_selected_cells, points * self.temp_multiplier))

        max_dist = math.dist((self.width / 2, self.height / 2),
                             (self.temp_circle.x, self.temp_circle.y)) + self.temp_circle.radius
        self.circumscribed_circle.radius = max(self.circumscribed_circle.radius, max_dist)
        self.temp_selected_cells = []
        self.temp_circle = None
        self.temp_multiplier = 1.0

        self.current_circles_count += 1

        SoundManager.instance().stop_sound(sounds.GROWING_CIRCLE)
        SoundManager.instance().play_sound(sound)

    def destroy_temp_circle(self, sound: str = ""):
        if self.temp_circle is None:
            return

        for cell in self.temp_selected_cells:
            cell.temp_selected = False
        self.temp_selected_cells = []

        self.temp_circle = None
        self.temp_multiplier = 1.0

        SoundManager.instance().stop_sound(sounds.GROWING_CIRCLE)
        if sound:
            SoundManager.instance().play_sound(sound)

    def remove_circle(self, v_circle: 'ValidatedCircle'):
        self.circles.remove(v_circle)

        cell_still_in_animation = 0
        for k, cell in enumerate(v_circle.contained_cells):
            if cell.animation is None:
                self.points -= cell.points
                self.max_circles_count_upgrade -= cell.cell_data.bonus_circles
                if cell.type == CellType.PACIFIER:
                    for c in cell.affected_cells:
                        if c.type in co.PACIFIED_INV_MAP:
                            c.change_type(co.PACIFIED_INV_MAP[c.type])
            else:
                cell_still_in_animation += 1
            cell.unselect(k)

        self.current_circles_count -= 1
        self.cells_in_animation -= cell_still_in_animation

        SoundManager.instance().play_sound(sounds.REMOVE_CIRCLE, volume=0.5)

    # endregion

    # region ===== UPDATE =====

    def on_cell_selected(self, cell: Cell):
        self.points += cell.points
        self.max_circles_count_upgrade += cell.cell_data.bonus_circles
        if cell.cell_data.bonus_circles > 0:
            SoundManager.instance().play_sound(sounds.BONUS_CIRCLE)

        self.cells_in_animation -= 1
        if cell.type == CellType.PACIFIER:
            for c in self._flood_fill(cell.x, cell.y):
                if c.type in co.PACIFIED_MAP:
                    c.change_type(co.PACIFIED_MAP[c.type])
                    cell.affected_cells.append(c)
        if self.points >= self.required_points[0]:
            self.countdown = 0.4

    def on_mouse_move(self, x: int, y: int, rel_x: int, rel_y: int):
        x_adj = x - self.x_offset
        y_adj = y - self.y_offset

        cell_x, cell_y = int(x_adj // self.cell_size), int(y_adj // self.cell_size)
        if 0 <= cell_x < len(self.terrain[0]) and 0 <= cell_y < len(self.terrain):
            cell: Cell | None = self.terrain[cell_y][cell_x]
            if cell is not None and cell is not self.hovered_cell:
                self.hovered_cell = cell
                cell.touch(x_adj, y_adj, rel_x, rel_y)
            self.hovered_cell = cell
        else:
            self.hovered_cell = None

        self.update_hovered_circle(x, y)

    def update_hovered_circle(self, x: int, y: int):
        x = x - self.x_offset
        y = y - self.y_offset

        if not self.circumscribed_circle.contains_point(x, y):
            for v_circle in self.circles:
                v_circle.circle.is_hovered = False
            return

        for v_circle in self.circles:
            v_circle.circle.is_hovered = v_circle.circle.contains_point(x, y)

    def update(self, dt: float):
        if self.is_finished():
            self.start_unloading_animation()

        self.update_temp_circle(dt)
        self.countdown -= dt

    def update_temp_circle(self, dt: float):
        if self.temp_circle is None:
            return

        self.temp_circle.radius += self.radius_inc_speed * dt

        for cell in self.cells:
            if self.temp_circle is None:
                break

            if not cell.selected and not cell.temp_selected:
                if self.temp_circle.contains_rect(cell.rect):
                    self.__on_cell_in_temp_circle(cell)
                elif self.temp_circle.touch_rect(cell.rect):
                    self.__on_cell_touch_temp_circle(cell)

        for v_circle in self.circles:
            if self.temp_circle is None:
                break

            if self.temp_circle.touch_circle(v_circle.circle):
                self.validate_temp_circle()
                break

    def __on_cell_touch_temp_circle(self, cell: Cell):
        if cell.type == CellType.BLOCKER:
            self.validate_temp_circle(sound=sounds.VALIDATE_CIRCLE_BLOCKER)

    def __on_cell_in_temp_circle(self, cell: Cell):
        if cell.cell_data.can_be_selected:
            cell.temp_select()
            self.temp_selected_cells.append(cell)
            self.temp_multiplier *= cell.cell_data.points_multiplier
        else:
            self.destroy_temp_circle(sounds.DESTROY_CIRCLE)

    def is_finished(self):
        return (self.animation == 0 and self.cells_in_animation <= 0
                and self.countdown <= 0 and self.points >= self.required_points[0])

    def draw(self, surface: pyg.Surface, scale: Scale, dt: float, up_down: float):
        if self.animation == 0:
            utils.draw_text_center(surface, f"Level {self.number + 1}", 140, scale.to_screen_rect(co.LEVEL_TITLE_RECT),
                                   co.MEDIUM_COLOR)
            self.draw_level(surface, scale, dt, up_down)
        elif self.animation == 1:
            utils.draw_text_center(surface, f"Level {self.number + 1}", 140, scale.to_screen_rect(co.LEVEL_TITLE_RECT),
                                   co.MEDIUM_COLOR)
            self.draw_loading_animation(surface, scale, dt)
        elif self.animation == -1:
            self.draw_unloading_animation(surface, scale, dt)

    def draw_level(self, surface: pyg.Surface, scale: Scale, dt: float, up_down: float):
        utils.draw_text_next_to_img(surface,
                                    textures.CELL_TEXTURES[0][1][co.TEXTURE_INDEX_FROM_SIZE[64]].get_current_sprite(),
                                    scale.to_screen_pos(*co.LEVEL_POINTS_COUNT_POS), int(15 * scale.scale),
                                    f'{self.points:.0f} / {self.required_points[0]:.0f}',
                                    64, co.MEDIUM_COLOR)

        circle_count = max(0, self.max_circles_count + self.max_circles_count_upgrade - self.current_circles_count)
        utils.draw_text_next_to_img(surface,
                                    textures.CIRCLE, scale.to_screen_pos(*co.CIRCLES_COUNT_POS),
                                    int(15 * scale.scale), str(circle_count),
                                    64, co.MEDIUM_COLOR if circle_count > 0 else co.DARK_RED_COLOR)

        if len(self.tutorials) == 1:
            utils.draw_text_center(surface, self.tutorials[0], 50, scale.to_screen_rect(co.LEVEL_TUTORIAL_11_RECT),
                                   co.MEDIUM_COLOR, up_down=up_down)
        elif len(self.tutorials) == 2:
            utils.draw_text_center(surface, self.tutorials[0], 50, scale.to_screen_rect(co.LEVEL_TUTORIAL_12_RECT),
                                   co.MEDIUM_COLOR, up_down=up_down)
            utils.draw_text_center(surface, self.tutorials[1], 50, scale.to_screen_rect(co.LEVEL_TUTORIAL_22_RECT),
                                   co.MEDIUM_COLOR, up_down=up_down)

        for cell in self.cells:
            cell.draw(surface, self.x_offset, self.y_offset, scale, dt)

        for v_circle in self.circles:
            v_circle.circle.draw(surface, self.x_offset, self.y_offset, scale)

        if self.temp_circle is not None:
            self.temp_circle.draw(surface, self.x_offset, self.y_offset, scale)

    # endregion

    # region ===== ANIMATIONS =====

    def start_loading_animation(self):
        for cell in self.cells:
            dir_x, dir_y = (cell.vector[0] + random.random() / 10, cell.vector[1] + random.random() / 10)
            x = cell.rect.x + dir_x * (co.WIDTH / 2 + 150)
            y = cell.rect.y + dir_y * (co.WIDTH / 2 + 150)
            cell.set_temp_rect(self.cell_size, x, y)
            speed = random.random() * 10 + 55
            cell.velocity = (-speed * dir_x, -speed * dir_y)
        self.animation = 1

        SoundManager.instance().play_sound(sounds.START_LEVEL)

    def draw_loading_animation(self, surface: pyg.Surface, scale: Scale, dt: float):
        placed_cells_count = 0
        for cell in self.cells:
            if cell.temp_rect is None:
                continue

            cell.draw(surface, self.x_offset, self.y_offset, scale, dt)
            if cell.is_in_place():
                cell.temp_rect = cell.rect
                placed_cells_count += 1
            else:
                cell.temp_rect.x += cell.velocity[0] * dt * 60
                cell.temp_rect.y += cell.velocity[1] * dt * 60

        if placed_cells_count == len(self.cells):
            LevelManager.instance().on_level_loaded()
            self.animation = 0

    def start_unloading_animation(self):
        for cell in self.cells:
            dir_x, dir_y = (cell.vector[0] + random.random() / 10, cell.vector[1] + random.random() / 10)
            cell.set_temp_rect(self.cell_size, cell.rect.x, cell.rect.y)
            speed = random.random() * 10 + 40
            cell.velocity = (speed * dir_x, speed * dir_y)
        self.animation = -1

        SoundManager.instance().play_sound(sounds.END_LEVEL)

    def draw_unloading_animation(self, surface: pyg.Surface, scale: Scale, dt: float):
        removed_cells_count = 0
        for cell in self.cells:
            if cell.temp_rect is None:
                continue

            cell.draw(surface, self.x_offset, self.y_offset, scale, dt)
            if cell.is_outside_screen(self.x_offset, self.y_offset):
                cell.displayed = False
                removed_cells_count += 1
            else:
                cell.temp_rect.x += cell.velocity[0] * dt * 60
                cell.temp_rect.y += cell.velocity[1] * dt * 60

        if removed_cells_count == len(self.cells):
            LevelManager.instance().on_level_unloaded()

    # endregion

    # region ===== OTHER =====

    def get_medals(self) -> list[int]:
        if len(self.required_points) == 1:
            return [1]
        if len(self.required_points) == 2:
            return [2, 1 if self.points >= self.required_points[1] else 0]
        if len(self.required_points) == 3:
            return [3, 2 if self.points >= self.required_points[1] else 0,
                    1 if self.points >= self.required_points[2] else 0]

    def got_gold_medal(self):
        return self.points >= self.required_points[-1]

    # endregion


class ValidatedCircle:
    def __init__(self, circle: Circle, contained_cells: list[Cell], points: float):
        self.circle = circle
        self.contained_cells = contained_cells
        self.points = points
