"""Developer helper: the model-space bone positions of the first frame of a .X animation
(the game's character animations, text or binary), to place seat and bed poses.
    python dev/xpose.py <anim.X> [bone ...]
DirectX conventions: row vectors, a bone's model transform = local x parent's."""
import re
import struct
import sys

import numpy as np


def text_tokens(text):
    text = re.sub(r"//[^\n]*|#[^\n]*", "", text)
    text = re.sub(r"<[0-9A-Fa-f-]+>", " ", text)     # GUIDs
    return re.findall(r"[A-Za-z_][\w.-]*|-?\d+\.?\d*(?:[eE][-+]?\d+)?|[{};,]", text)


def binary_tokens(data, float_size):
    """The binary .X token stream as the same tokens the text reader gives."""
    out = []
    i = 16
    fmt, fsize = ("<d", 8) if float_size == 64 else ("<f", 4)
    while i + 2 <= len(data):
        token = struct.unpack_from("<H", data, i)[0]
        i += 2
        if token == 1:                                  # name
            n = struct.unpack_from("<I", data, i)[0]
            out.append(data[i + 4:i + 4 + n].decode("latin-1"))
            i += 4 + n
        elif token == 2:                                # string, then a ';' or ',' token
            n = struct.unpack_from("<I", data, i)[0]
            out.append(data[i + 4:i + 4 + n].decode("latin-1"))
            i += 4 + n
        elif token == 3:                                # integer
            out.append(str(struct.unpack_from("<I", data, i)[0]))
            i += 4
        elif token == 5:                                # GUID
            i += 16
        elif token == 6:                                # integer list
            n = struct.unpack_from("<I", data, i)[0]
            out.extend(str(v) for v in struct.unpack_from("<%dI" % n, data, i + 4))
            i += 4 + 4 * n
        elif token == 7:                                # float list
            n = struct.unpack_from("<I", data, i)[0]
            out.extend(repr(v) for v in struct.unpack_from("<%d%s" % (n, fmt[1]), data, i + 4))
            i += 4 + fsize * n
        elif token == 10:
            out.append("{")
        elif token == 11:
            out.append("}")
        elif token == 19:
            out.append(",")
        elif token == 20:
            out.append(";")
        elif token == 31:
            out.append("template")
        else:
            out.append("#%d" % token)                   # keywords inside templates
    return out


def tokens(path):
    data = open(path, "rb").read()
    kind, float_size = data[8:12].decode("ascii"), int(data[12:16])
    if kind == "bin ":
        return binary_tokens(data, float_size)
    return text_tokens(data.decode("latin-1"))


class Parser:
    def __init__(self, toks):
        self.t = toks
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def next(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def numbers(self, count):
        out = []
        while len(out) < count:
            tok = self.next()
            if tok in (";", ","):
                continue
            out.append(float(tok))
        return out

    def skip_block(self):
        """At or before a '{': skips to its matching '}'."""
        while self.next() != "{":
            pass
        depth = 1
        while depth:
            tok = self.next()
            if tok == "{":
                depth += 1
            elif tok == "}":
                depth -= 1

    def frames(self, parent, out):
        """At 'Frame name {': reads the frame and its children."""
        self.next()                          # Frame
        name = self.next()
        assert self.next() == "{", name
        local = np.eye(4)
        while self.peek() != "}":
            tok = self.peek()
            if tok == "FrameTransformMatrix":
                self.next()
                assert self.next() == "{"
                local = np.array(self.numbers(16)).reshape(4, 4)
                while self.next() != "}":
                    pass
            elif tok == "Frame":
                self.frames(name, out)
            else:
                self.skip_block()            # meshes and the like
        self.next()                          # }
        out[name] = (parent, local)

    def animation(self, keys):
        """At 'Animation [name] {': reads the bone reference and its first key."""
        self.next()
        if self.peek() != "{":
            self.next()
        assert self.next() == "{"
        bone = None
        while self.peek() != "}":
            tok = self.next()
            if tok == "{":
                bone = self.next()
                assert self.next() == "}"
            elif tok == "AnimationKey":
                if self.peek() != "{":
                    self.next()
                assert self.next() == "{"
                kind = int(self.numbers(1)[0])
                count = int(self.numbers(1)[0])
                first = None
                for k in range(count):
                    time, n = self.numbers(2)
                    values = self.numbers(int(n))
                    if first is None:
                        first = values
                while self.next() != "}":
                    pass
                keys.setdefault(bone, {})[kind] = first
            elif tok in ("AnimationOptions",):
                self.skip_block()
        self.next()


def load(path):
    p = Parser(tokens(path))
    frames, keys = {}, {}
    while p.peek() is not None:
        tok = p.peek()
        if tok == "template":
            p.skip_block()
        elif tok == "Frame":
            p.frames(None, frames)
        elif tok == "Animation":
            p.animation(keys)
        elif tok == "AnimationSet":
            p.next()
            if p.peek() != "{":
                p.next()
            p.next()   # {  (its Animations follow at this level)
        else:
            p.next()
    return frames, keys


def quat_matrix(w, x, y, z):
    # row-vector rotation matrix of a unit quaternion
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y + w * z), 2 * (x * z - w * y), 0],
        [2 * (x * y - w * z), 1 - 2 * (x * x + z * z), 2 * (y * z + w * x), 0],
        [2 * (x * z + w * y), 2 * (y * z - w * x), 1 - 2 * (x * x + y * y), 0],
        [0, 0, 0, 1]])


def pose(path):
    frames, keys = load(path)
    local = {}
    for name, (parent, m) in frames.items():
        k = keys.get(name, {})
        if 4 in k:
            m = np.array(k[4]).reshape(4, 4)
        elif k:
            s = np.diag([*(k.get(1) or (1, 1, 1)), 1.0])
            # the files' quaternions rotate the other way round (checked against their
            # own frame matrices): use the conjugate
            w, x, y, z = k[0] if 0 in k else (1.0, 0.0, 0.0, 0.0)
            r = quat_matrix(w, -x, -y, -z)
            t = np.eye(4)
            if 2 in k:
                t[3, :3] = k[2]
            m = s @ r @ t
        local[name] = (parent, m)
    world = {}

    def resolve(name):
        if name not in world:
            parent, m = local[name]
            world[name] = m @ resolve(parent) if parent else m
        return world[name]

    for name in local:
        resolve(name)
    return {name: m[3, :3] for name, m in world.items()}, {n: sorted(k) for n, k in keys.items()}


if __name__ == "__main__":
    positions, kinds = pose(sys.argv[1])
    wanted = sys.argv[2:] or sorted(positions)
    print("key kinds:", sorted({tuple(v) for v in kinds.values()}))
    for name in wanted:
        if name in positions:
            x, y, z = positions[name]
            print("%-18s %8.4f %8.4f %8.4f" % (name, x, y, z))
