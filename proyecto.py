import glfw
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import cv2
import pygame
import os
import sys
from mutagen.mp3 import MP3
from ffpyplayer.player import MediaPlayer


# === CONFIGURACIÓN ===
video_path = "video.mp4"
cover_path = "cover.png"  # Imagen de portada del álbum
audio_path = "audio.mp3"
audio_duration = 1  # valor por defecto para evitar división por cero

# === VÉRTICES DEL CUBO ===
vertices = np.array([
    [-1, -1,  1],  # 0
    [ 1, -1,  1],  # 1
    [ 1,  1,  1],  # 2
    [-1,  1,  1],  # 3
    [-1, -1, -1],  # 4
    [ 1, -1, -1],  # 5
    [ 1,  1, -1],  # 6
    [-1,  1, -1],  # 7
], dtype=np.float32)

caras_visibles = [
    [0, 1, 2, 3],  # Frente
    [1, 5, 6, 2],  # Derecha (controles)
    [3, 2, 6, 7],  # Superior (video/portada)
]

selected_vertex = None
window_width, window_height = 1000, 800
is_playing = False
texture_id = None
control_texture_id = None
cap = None
video_fps = 30
start_time = 0
volume = 0.7
control_texture_size = 512
font = None
pygame_font = None

def init_window():
    global window_width, window_height, font, pygame_font
    
    if not glfw.init():
        raise Exception("GLFW initialization failed")

    window = glfw.create_window(window_width, window_height, "Spotify Cube Player", None, None)
    if not window:
        glfw.terminate()
        raise Exception("Window creation failed")

    glfw.make_context_current(window)
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_TEXTURE_2D)
    
    # Configuración de fuentes
    pygame.init()
    pygame_font = pygame.font.SysFont('Arial', 24)
    font = pygame_font  # Para compatibilidad

    glfw.set_mouse_button_callback(window, mouse_button_callback)
    glfw.set_cursor_pos_callback(window, mouse_motion_callback)
    glfw.set_key_callback(window, key_callback)
    glfw.set_window_size_callback(window, window_size_callback)

    return window

def window_size_callback(window, width, height):
    global window_width, window_height
    window_width, window_height = width, height
    glViewport(0, 0, width, height)

def init_audio_video():
    global cap, texture_id, control_texture_id, player, video_fps

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Error: No se pudo abrir el video {video_path}")
        sys.exit(1)

    video_fps = cap.get(cv2.CAP_PROP_FPS)

    # Audio embebido
    player = MediaPlayer(video_path)
    
    # Texturas
    texture_id = glGenTextures(1)
    control_texture_id = glGenTextures(1)
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

    glBindTexture(GL_TEXTURE_2D, control_texture_id)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
    glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)

    load_cover_texture()


def load_cover_texture():
    """Carga la imagen de portada como textura"""
    img = cv2.imread(cover_path)
    if img is None:
        print(f"Error: No se pudo cargar la imagen {cover_path}")
        # Crear una imagen de respaldo
        img = np.zeros((512, 512, 3), dtype=np.uint8)
        cv2.putText(img, "COVER ART", (50, 256), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 4)
    
    img = cv2.flip(img, 0)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    h, w, _ = img.shape
    
    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, w, h, 0, GL_RGB, GL_UNSIGNED_BYTE, img)

def update_video_texture():
    global cap, player, is_playing

    if not is_playing or not cap:
        return

    frame, val = player.get_frame()
    if val == 'eof':
        return

    if frame is None:
        return

    img, t = frame
    frame = img.to_ndarray(format='rgb24')

    h, w, _ = frame.shape
    frame = cv2.flip(frame, 0)

    glBindTexture(GL_TEXTURE_2D, texture_id)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, w, h, 0, GL_RGB, GL_UNSIGNED_BYTE, frame)

def update_control_texture():
    """Actualiza la textura de la interfaz de control"""
    global control_texture_id, control_texture_size, is_playing, volume
    
    # Crear superficie de pygame
    surface = pygame.Surface((control_texture_size, control_texture_size), pygame.SRCALPHA)
    surface.fill((40, 40, 40, 230))  # Fondo semi-transparente
    
    # Dibujar barra de progreso
    if is_playing:
        current_time = glfw.get_time() - start_time
    else:
        current_time = 0
    
    total_time = audio_duration
    if total_time <= 0:
        total_time = 1  # evitar división por cero
    
    progress = current_time / total_time
    bar_width = control_texture_size * 0.8
    bar_height = 10
    bar_x = (control_texture_size - bar_width) // 2
    bar_y = 50
    
    # Barra de fondo
    pygame.draw.rect(surface, (100, 100, 100), (bar_x, bar_y, bar_width, bar_height))
    # Barra de progreso
    pygame.draw.rect(surface, (30, 215, 96), (bar_x, bar_y, bar_width * progress, bar_height))
    
    # Dibujar tiempo
    mins, secs = divmod(int(current_time), 60)
    time_text = f"{mins:02d}:{secs:02d}"
    text_surface = pygame_font.render(time_text, True, (255, 255, 255))
    surface.blit(text_surface, (bar_x, bar_y + 20))
    
    # Dibujar botones
    button_size = 60
    button_y = control_texture_size // 2
    
    # Botón de retroceso
    rewind_rect = pygame.Rect(control_texture_size//2 - button_size*2, button_y, button_size, button_size)
    pygame.draw.rect(surface, (70, 70, 70), rewind_rect, border_radius=10)
    pygame.draw.polygon(surface, (200, 200, 200), [
        (rewind_rect.centerx - 10, rewind_rect.centery),
        (rewind_rect.centerx - 10, rewind_rect.centery - 15),
        (rewind_rect.centerx + 5, rewind_rect.centery)
    ])
    
    # Botón de play/pause
    play_rect = pygame.Rect(control_texture_size//2 - button_size//2, button_y, button_size, button_size)
    pygame.draw.rect(surface, (30, 215, 96), play_rect, border_radius=10)
    if is_playing:
        # Pausa: dos barras
        pygame.draw.rect(surface, (255, 255, 255), (play_rect.centerx - 15, play_rect.centery - 15, 10, 30))
        pygame.draw.rect(surface, (255, 255, 255), (play_rect.centerx + 5, play_rect.centery - 15, 10, 30))
    else:
        # Play: triángulo
        pygame.draw.polygon(surface, (255, 255, 255), [
            (play_rect.centerx - 10, play_rect.centery - 15),
            (play_rect.centerx - 10, play_rect.centery + 15),
            (play_rect.centerx + 15, play_rect.centery)
        ])
    
    # Botón de avance
    forward_rect = pygame.Rect(control_texture_size//2 + button_size, button_y, button_size, button_size)
    pygame.draw.rect(surface, (70, 70, 70), forward_rect, border_radius=10)
    pygame.draw.polygon(surface, (200, 200, 200), [
        (forward_rect.centerx + 10, forward_rect.centery),
        (forward_rect.centerx + 10, forward_rect.centery - 15),
        (forward_rect.centerx - 5, forward_rect.centery)
    ])
    
    # Control de volumen
    vol_width = control_texture_size * 0.7
    vol_height = 20
    vol_x = (control_texture_size - vol_width) // 2
    vol_y = control_texture_size - 80
    
    # Barra de volumen
    pygame.draw.rect(surface, (100, 100, 100), (vol_x, vol_y, vol_width, vol_height))
    pygame.draw.rect(surface, (30, 215, 96), (vol_x, vol_y, vol_width * volume, vol_height))
    
    # Indicador de volumen
    vol_pos = vol_x + vol_width * volume
    pygame.draw.circle(surface, (200, 200, 200), (int(vol_pos), vol_y + vol_height//2), 12)
    
    # Convertir la superficie a un array de numpy
    data = pygame.image.tostring(surface, "RGBA", True)
    img = np.frombuffer(data, dtype=np.uint8).reshape((control_texture_size, control_texture_size, 4))
    img = np.flipud(img)  # Invertir verticalmente
    
    # Cargar la textura
    glBindTexture(GL_TEXTURE_2D, control_texture_id)
    glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, control_texture_size, control_texture_size, 0, 
                 GL_RGBA, GL_UNSIGNED_BYTE, img)

def draw_cube():
    colors = [(0.1, 0.1, 0.1), (0.15, 0.15, 0.15)]  # Colores oscuros estilo Spotify
    
    for i, cara in enumerate(caras_visibles):
        if i == 2:  # Cara superior (video/portada)
            glBindTexture(GL_TEXTURE_2D, texture_id)
            glColor3f(1, 1, 1)
            glBegin(GL_QUADS)
            glTexCoord2f(0, 0); glVertex3fv(vertices[cara[0]])
            glTexCoord2f(1, 0); glVertex3fv(vertices[cara[1]])
            glTexCoord2f(1, 1); glVertex3fv(vertices[cara[2]])
            glTexCoord2f(0, 1); glVertex3fv(vertices[cara[3]])
            glEnd()
        elif i == 1:  # Cara derecha (controles)
            glBindTexture(GL_TEXTURE_2D, control_texture_id)
            glColor3f(1, 1, 1)
            glBegin(GL_QUADS)
            glTexCoord2f(0, 0); glVertex3fv(vertices[cara[0]])
            glTexCoord2f(1, 0); glVertex3fv(vertices[cara[1]])
            glTexCoord2f(1, 1); glVertex3fv(vertices[cara[2]])
            glTexCoord2f(0, 1); glVertex3fv(vertices[cara[3]])
            glEnd()
        else:
            glColor3fv(colors[i])
            glBegin(GL_QUADS)
            for idx in cara:
                glVertex3fv(vertices[idx])
            glEnd()
    
    # Dibujar HUD
    draw_hud()

def draw_hud():
    """Dibuja la interfaz de usuario en 2D"""
    # Configurar proyección ortográfica
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, window_width, 0, window_height, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    
    # Dibujar tiempo transcurrido
    if is_playing:
        current_time = glfw.get_time() - start_time
    else:
        current_time = 0
    
    mins, secs = divmod(int(current_time), 60)
    time_text = f"{mins:02d}:{secs:02d}"
    
    text_surface = pygame_font.render(time_text, True, (255, 255, 255))
    text_data = pygame.image.tostring(text_surface, "RGBA", True)
    
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glRasterPos2f(20, 40)
    glDrawPixels(text_surface.get_width(), text_surface.get_height(), 
                 GL_RGBA, GL_UNSIGNED_BYTE, text_data)
    
    # Indicador de volumen
    vol_text = f"Vol: {int(volume * 100)}%"
    vol_surface = pygame_font.render(vol_text, True, (255, 255, 255))
    vol_data = pygame.image.tostring(vol_surface, "RGBA", True)
    glRasterPos2f(20, 80)
    glDrawPixels(vol_surface.get_width(), vol_surface.get_height(), 
                 GL_RGBA, GL_UNSIGNED_BYTE, vol_data)
    
    glDisable(GL_BLEND)
    
    # Restaurar matrices anteriores
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glPopMatrix()

def mouse_button_callback(window, button, action, mods):
    global selected_vertex, is_playing, start_time, volume

    if button == glfw.MOUSE_BUTTON_LEFT:
        if action == glfw.PRESS:
            x, y = glfw.get_cursor_pos(window)
            y = window_height - y  # Invertir coordenada Y
            
            # Comprobar si se hizo clic en los controles
            handle_control_click(x, y)
            
            selected_vertex = pick_vertex(x, y)
        elif action == glfw.RELEASE:
            selected_vertex = None

def handle_control_click(x, y):
    global is_playing, start_time, volume
    
    # Coordenadas relativas al centro de la ventana
    rel_x = x - window_width / 2
    rel_y = y - window_height / 2
    
    # Tamaño aproximado de la cara de controles en pantalla
    control_size = min(window_width, window_height) * 0.4
    
    # Verificar si el clic está dentro del área de la cara de controles
    if abs(rel_x) < control_size and abs(rel_y) < control_size:
        # Convertir a coordenadas UV de la textura (0 a 1)
        u = (rel_x + control_size) / (2 * control_size)
        v = (rel_y + control_size) / (2 * control_size)
        
        # Coordenadas en la textura de controles
        tex_x = int(u * control_texture_size)
        tex_y = int((1 - v) * control_texture_size)  # Invertir Y
        
        # Detectar clic en botones (coordenadas aproximadas)
        button_size = 60
        button_y = control_texture_size // 2
        
        # Botón de retroceso
        rewind_x1 = control_texture_size//2 - button_size*2
        rewind_x2 = rewind_x1 + button_size
        rewind_y1 = button_y
        rewind_y2 = button_y + button_size
        
        # Botón de play/pause
        play_x1 = control_texture_size//2 - button_size//2
        play_x2 = play_x1 + button_size
        play_y1 = button_y
        play_y2 = button_y + button_size
        
        # Botón de avance
        forward_x1 = control_texture_size//2 + button_size
        forward_x2 = forward_x1 + button_size
        forward_y1 = button_y
        forward_y2 = button_y + button_size
        
        # Control de volumen
        vol_y = control_texture_size - 80
        vol_x1 = (control_texture_size - control_texture_size * 0.7) // 2
        vol_x2 = vol_x1 + control_texture_size * 0.7
        
        # Verificar clic en controles
        if rewind_x1 <= tex_x <= rewind_x2 and rewind_y1 <= tex_y <= rewind_y2:
            # Retroceder 10 segundos
            if is_playing:
                current_time = glfw.get_time() - start_time
                new_time = max(0, current_time - 10)
                start_time = glfw.get_time() - new_time
                pygame.mixer.music.set_pos(new_time)
        
        elif play_x1 <= tex_x <= play_x2 and play_y1 <= tex_y <= play_y2:
            # Play/Pause
            is_playing = not is_playing
            if is_playing:
                pygame.mixer.music.unpause()
                if pygame.mixer.music.get_pos() == -1:  # Si no estaba reproduciendo
                    pygame.mixer.music.play()
                    start_time = glfw.get_time()
            else:
                pygame.mixer.music.pause()
                load_cover_texture()  # Mostrar portada
        
        elif forward_x1 <= tex_x <= forward_x2 and forward_y1 <= tex_y <= forward_y2:
            # Avanzar 10 segundos
            if is_playing:
                current_time = glfw.get_time() - start_time
                total_time = pygame.mixer.music.get_length() / 1000.0
                new_time = min(total_time, current_time + 10)
                start_time = glfw.get_time() - new_time
                pygame.mixer.music.set_pos(new_time)
        
        elif vol_x1 <= tex_x <= vol_x2 and vol_y - 20 <= tex_y <= vol_y + 20:
            # Ajustar volumen
            vol_pos = (tex_x - vol_x1) / (vol_x2 - vol_x1)
            volume = max(0.0, min(1.0, vol_pos))
            pygame.mixer.music.set_volume(volume)

def key_callback(window, key, scancode, action, mods):
    global is_playing, start_time, volume
    
    if action == glfw.PRESS:
        if key == glfw.KEY_SPACE:  # Barra espaciadora para play/pause
            is_playing = not is_playing
            if is_playing:
                pygame.mixer.music.play()
                start_time = glfw.get_time()
            else:
                pygame.mixer.music.pause()
                load_cover_texture()
        
        elif key == glfw.KEY_LEFT:  # Retroceder 10 segundos
            if is_playing:
                current_time = glfw.get_time() - start_time
                new_time = max(0, current_time - 10)
                start_time = glfw.get_time() - new_time
                pygame.mixer.music.set_pos(new_time)
        
        elif key == glfw.KEY_RIGHT:  # Avanzar 10 segundos
            if is_playing:
                current_time = glfw.get_time() - start_time
                total_time = pygame.mixer.music.get_length() / 1000.0
                new_time = min(total_time, current_time + 10)
                start_time = glfw.get_time() - new_time
                pygame.mixer.music.set_pos(new_time)
        
        elif key == glfw.KEY_UP:  # Aumentar volumen
            volume = min(1.0, volume + 0.1)
            pygame.mixer.music.set_volume(volume)
        
        elif key == glfw.KEY_DOWN:  # Disminuir volumen
            volume = max(0.0, volume - 0.1)
            pygame.mixer.music.set_volume(volume)

def mouse_motion_callback(window, xpos, ypos):
    global vertices, selected_vertex
    
    if selected_vertex is None:
        return

    modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
    projection = glGetDoublev(GL_PROJECTION_MATRIX)
    viewport = glGetIntegerv(GL_VIEWPORT)

    winX = xpos
    winY = viewport[3] - ypos
    winZ = glReadPixels(int(winX), int(winY), 1, 1, GL_DEPTH_COMPONENT, GL_FLOAT)

    world_coords = gluUnProject(winX, winY, winZ[0][0], modelview, projection, viewport)
    if world_coords:
        vertices[selected_vertex] = world_coords[:3]

def pick_vertex(x, y, threshold=15):
    modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
    projection = glGetDoublev(GL_PROJECTION_MATRIX)
    viewport = glGetIntegerv(GL_VIEWPORT)

    closest_idx = None
    min_dist = threshold
    for i, v in enumerate(vertices):
        screen_coords = gluProject(v[0], v[1], v[2], modelview, projection, viewport)
        dx = screen_coords[0] - x
        dy = (viewport[3] - screen_coords[1]) - y
        dist = np.hypot(dx, dy)
        if dist < min_dist:
            closest_idx = i
            min_dist = dist
    return closest_idx

def main():
    global window_width, window_height
    
    window = init_window()
    init_audio_video()
    
    glfw.get_framebuffer_size(window)
    glViewport(0, 0, window_width, window_height)
    
    while not glfw.window_should_close(window):
        glfw.poll_events()
        glClearColor(0.08, 0.08, 0.08, 1.0) 
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        gluPerspective(45, window_width / window_height, 0.1, 50.0)
        rot_x, rot_y = 35, -45
        glTranslatef(0.0, 0.0, -7)
        glRotatef(rot_x, 1, 0, 0)
        glRotatef(rot_y, 0, 1, 0)
        update_video_texture()
        update_control_texture()
        draw_cube()
        glfw.swap_buffers(window)

    if cap and cap.isOpened():
        cap.release()
    pygame.mixer.quit()
    glfw.terminate()

if __name__ == "__main__":
    main()