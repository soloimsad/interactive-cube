import glfw
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
import cv2
from ffpyplayer.player import MediaPlayer
import glm
import time

# Helper para chequear errores de OpenGL
def check_gl_error(label="GL_ERROR"):
    err = glGetError()
    if err != GL_NO_ERROR:
        print(f"{label}: {gluErrorString(err)} (0x{err:04X})")

class Texture:
    def __init__(self, path, flip=True):
        self.id = glGenTextures(1)
        self.load(path, flip)

    def load(self, path, flip=True):
        img = cv2.imread(path)
        if img is None:
            raise ValueError(f"No se pudo cargar la textura: {path}")
        if flip:
            img = cv2.flip(img, 0)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w, _ = img.shape

        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.id)
        check_gl_error("After bind Texture.load")
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, w, h, 0, GL_RGB, GL_UNSIGNED_BYTE, img)
        check_gl_error("After texImage2D Texture.load")

    def bind(self):
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.id)
        check_gl_error("After bind Texture.bind")

class VideoPlayer:
    def __init__(self, video_path):
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            raise ValueError(f"No se pudo abrir el video: {video_path}")
        self.audio_player = MediaPlayer(video_path)
        self.texture_id = glGenTextures(1)
        self.frame_size = None
        self._init_texture()
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.last_frame_time = time.time()

    def _init_texture(self):
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        check_gl_error("After bind VideoPlayer._init_texture")
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        dummy = np.zeros((1,1,3), dtype=np.uint8)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGB, 1, 1, 0, GL_RGB, GL_UNSIGNED_BYTE, dummy)
        check_gl_error("After texImage2D VideoPlayer._init_texture")

    def update(self):
        audio_frame, audio_val = self.audio_player.get_frame()
        now = time.time()
        if now - self.last_frame_time < 1.0/self.fps:
            return
        self.last_frame_time = now
        ret, frame = self.cap.read()
        if not ret:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            return
        img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = np.flipud(img)
        h, w, _ = img.shape
        gl_format = GL_RGB
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        check_gl_error("After bind VideoPlayer.update")
        glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
        glTexImage2D(GL_TEXTURE_2D, 0, gl_format, w, h, 0, gl_format, GL_UNSIGNED_BYTE, img)
        check_gl_error("After texImage2D VideoPlayer.update")
        self.frame_size = (w, h)

    def bind(self):
        glActiveTexture(GL_TEXTURE0)
        glBindTexture(GL_TEXTURE_2D, self.texture_id)
        check_gl_error("After bind VideoPlayer.bind")

    def release(self):
        if hasattr(self, 'cap'):
            self.cap.release()
        if hasattr(self, 'audio_player'):
            self.audio_player.close_player()
        glDeleteTextures([self.texture_id])

class Cube:
    def __init__(self):
        self.vertices = np.array([
            [-1, -1,  1], [ 1, -1,  1], [ 1,  1,  1], [-1,  1,  1],
            [-1, -1, -1], [ 1, -1, -1], [ 1,  1, -1], [-1,  1, -1],
        ], dtype=np.float32)
        self.faces = {
            'frente': [0,1,2,3],
            'derecha': [1,5,6,2],
            'arriba': [3,2,6,7]
        }

    def draw_face(self, face_name, texture):
        glEnable(GL_TEXTURE_2D)
        glColor3f(1.0,1.0,1.0)
        texture.bind()
        glBegin(GL_QUADS)
        tex_coords = [(0,0),(1,0),(1,1),(0,1)]
        for i, idx in enumerate(self.faces[face_name]):
            glTexCoord2f(*tex_coords[i])
            glVertex3fv(self.vertices[idx])
        glEnd()
        glDisable(GL_TEXTURE_2D)

    def draw_vertices(self):
        glPointSize(8)
        glBegin(GL_POINTS)
        glColor3f(1,0,0)
        for v in self.vertices:
            glVertex3fv(v)
        glEnd()
        glColor3f(1,1,1)

    def pick_vertex(self, x, y, view, projection, threshold=15):
        glFlush()
        viewport = glGetIntegerv(GL_VIEWPORT)
        closest = None
        min_dist = threshold
        for i, vert in enumerate(self.vertices):
            sc = glm.project(glm.vec3(*vert), view, projection, glm.vec4(*viewport))
            dx = x - sc.x
            dy = (viewport[3] - y) - sc.y
            dist = np.hypot(dx, dy)
            if dist < min_dist:
                min_dist = dist
                closest = i
        return closest

class InteractiveCubeApp:
    def framebuffer_size_callback(self, window, width, height):
        self.width = width
        self.height = height
        glViewport(0, 0, width, height)

    def __init__(self, width=800, height=600):
        self.width = width
        self.height = height
        self.window = None
        self.cube = Cube()
        self.selected_vertex = None
        self.textures = {}
        self.video_player = None
        self.zoom = -6.0  # Zoom inicial
        self.image_paths = {'frente':'cover.png','derecha':'cover.png'}
        self.video_path = 'video.mp4'

    def init_glfw(self):
        if not glfw.init():
            raise RuntimeError("No se pudo inicializar GLFW")
        self.window = glfw.create_window(
            self.width,
            self.height,
            "Cubo 3D Interactivo",
            None,
            None
        )
        if not self.window:
            glfw.terminate()
            raise RuntimeError("No se pudo crear la ventana")
        glfw.make_context_current(self.window)
        glfw.set_mouse_button_callback(self.window, self.mouse_button_callback)
        glfw.set_cursor_pos_callback(self.window, self.mouse_motion_callback)
        glfw.set_scroll_callback(self.window, self.scroll_callback)
        glfw.set_framebuffer_size_callback(self.window, self.framebuffer_size_callback)
        glEnable(GL_DEPTH_TEST)
        glClearColor(0.0, 0.0, 0.0, 1.0)

    def load_resources(self):
        for face, path in self.image_paths.items():
            self.textures[face] = Texture(path)
        self.video_player = VideoPlayer(self.video_path)

    def mouse_button_callback(self, window, button, action, mods):
        if button == glfw.MOUSE_BUTTON_LEFT:
            x,y = glfw.get_cursor_pos(window)
            proj = glm.perspective(glm.radians(45), self.width/self.height, 0.1, 50)
            view = glm.translate(glm.mat4(1), glm.vec3(0,0,self.zoom))
            view = glm.rotate(view, glm.radians(30), glm.vec3(1,0,0))
            view = glm.rotate(view, glm.radians(-45), glm.vec3(0,1,0))
            if action == glfw.PRESS:
                self.selected_vertex = self.cube.pick_vertex(x,y,view,proj)
            else:
                self.selected_vertex = None

    def mouse_motion_callback(self, window, xpos, ypos):
        if self.selected_vertex is None:
            return
        viewport = glGetIntegerv(GL_VIEWPORT)
        proj = glm.perspective(glm.radians(45), self.width/self.height, 0.1, 50)
        view = glm.translate(glm.mat4(1), glm.vec3(0,0,self.zoom))
        view = glm.rotate(view, glm.radians(30), glm.vec3(1,0,0))
        view = glm.rotate(view, glm.radians(-45), glm.vec3(0,1,0))
        old_world = self.cube.vertices[self.selected_vertex]
        screen_pos = glm.project(glm.vec3(*old_world), view, proj, glm.vec4(*viewport))
        new_world = glm.unProject(glm.vec3(xpos, viewport[3] - ypos, screen_pos.z), view, proj, glm.vec4(*viewport))
        self.cube.vertices[self.selected_vertex] = [new_world.x, new_world.y, new_world.z]

    def scroll_callback(self, window, xoffset, yoffset):
        self.zoom += yoffset * 0.5
        self.zoom = max(-30.0, min(-2.0, self.zoom))

    def setup_proj(self):
        glViewport(0, 0, self.width, self.height)
        glMatrixMode(GL_PROJECTION)
        proj = glm.perspective(glm.radians(45), self.width/self.height, 0.1, 50.0)
        glLoadMatrixf(np.array(proj.to_list(), dtype=np.float32))
        glMatrixMode(GL_MODELVIEW)
        mv = glm.translate(glm.mat4(1), glm.vec3(0,0,self.zoom))
        mv = glm.rotate(mv, glm.radians(30), glm.vec3(1,0,0))
        mv = glm.rotate(mv, glm.radians(-45), glm.vec3(0,1,0))
        glLoadMatrixf(np.array(mv.to_list(), dtype=np.float32))

    def render(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        self.setup_proj()
        self.video_player.update()
        self.cube.draw_face('frente', self.textures['frente'])
        self.cube.draw_face('derecha', self.textures['derecha'])
        self.cube.draw_face('arriba', self.video_player)
        self.cube.draw_vertices()

    def run(self):
        try:
            self.init_glfw()
            self.load_resources()
            while not glfw.window_should_close(self.window):
                glfw.poll_events()
                self.render()
                glfw.swap_buffers(self.window)
        finally:
            self.cleanup()

    def cleanup(self):
        if self.video_player:
            self.video_player.release()
        glDeleteTextures([t.id for t in self.textures.values()])
        if self.window:
            glfw.destroy_window(self.window)
        glfw.terminate()

if __name__ == '__main__':
    app = InteractiveCubeApp()
    app.run()
