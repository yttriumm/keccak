from __future__ import annotations

from typing import List, Iterable, Tuple, Callable
from itertools import product

Bit = int
Bit3DMatrix = List[List[List[int]]]
BitList = List[Bit]
b_to_l = {25: 0, 50: 1, 100: 2, 200: 3, 400: 4, 800: 5, 1600: 6}


def pad(m: int, r: int) -> BitList:
    j = (-m - 2) % r
    return [1] + [0] * j + [1]


def two_d_product(dim1, dim2) -> Iterable[Tuple[int, int]]:
    return product(range(dim1), range(dim2))


def rc(t):
    if t % 255 == 0:
        return 1
    R = [1] + [0] * 7
    for i in range(1, (t % 255) + 1):
        R = [0] + R
        R[0] ^= R[8]
        R[4] ^= R[8]
        R[5] ^= R[8]
        R[6] ^= R[8]
        R = R[0:8]
    return R[0]


class State:
    def __init__(self, b: int):
        self.b = b
        self.w = b // 25
        try:
            self.l = b_to_l[b]
        except KeyError:
            raise Exception(f"The state size must be one of: {b_to_l.values()}.")
        self.A = [
            [
                [0 for _ in range(self.w)]
                for _ in range(5)
            ]
            for _ in range(5)
        ]

    @staticmethod
    def from_S(S: BitList) -> State:
        state = State(len(S))
        for x, y, z in product(range(5), range(5), range(state.w)):
            state.A[x][y][z] = S[state.w * (5 * y + x) + z]
        print(state.A[1][1][63] == S[447])
        return state

    @property
    def points(self):
        return product(range(5), range(5), range(self.w))

    def to_S(self) -> BitList:
        S = [0] * self.b
        for x, y, z in self.points:
            S[self.w * (5 * y + x) + z] = self.A[x][y][z]
        return S

    def copy(self) -> State:
        state = State(self.b)
        for x, y, z in self.points:
            state.A[x][y][z] = self.A[x][y][z]
        return state


def theta(state: State) -> State:
    w = state.w
    A = state.A
    new_state = state.copy()

    C = [[0 for _ in range(w)] for _ in range(5)]
    D = [[0 for _ in range(w)] for _ in range(5)]

    for x, z in two_d_product(5, w):
        C[x][z] = A[x][0][z] ^ A[x][1][z] ^ A[x][2][z] ^ A[x][3][z] ^ A[x][4][z]
    for x, z in two_d_product(5, w):
        D[x][z] = C[(x - 1) % 5][z] ^ C[(x + 1) % 5][(z - 1) % w]
    for x, y, z in new_state.points:
        new_state.A[x][y][z] = A[x][y][z] ^ D[x][z]
    return new_state


def rho(state: State) -> State:
    w = state.w
    A = state.A
    new_state = state.copy()

    x, y = 1, 0
    for t in range(24):
        for z in range(w):
            new_state.A[x][y][z] = A[x][y][(z - (t + 1) * (t + 2) // 2) % w]
            x, y = y, (2 * x + 3 * y) % 5
    return new_state


def pi(state: State) -> State:
    A = state.A
    new_state = state.copy()
    for x, y, z in new_state.points:
        new_state.A[x][y][z] = A[(x + 3 * y) % 5][x][z]

    return new_state


def chi(state: State) -> State:
    new_state = state.copy()
    A = state.A
    for x, y, z in new_state.points:
        new_state.A[x][y][z] = A[x][y][z] ^ ((A[(x + 1) % 5][y][z] ^ 1) * (A[(x + 2) % 5][y][z]))
    return state


def iota(state: State, ir: int) -> State:
    new_state = state.copy()
    w = new_state.w
    l = new_state.l
    RC = [0] * w
    for j in range(0, l + 1):
        RC[2 ** j - 1] = rc(j + 7 * ir)
    for z in range(w):
        new_state.A[0][0][z] ^= RC[z]
    return state


def rnd(state: State, ir: int) -> State:
    return iota(chi(pi(rho(theta(state)))), ir)


def keccak_p(nr: int, S: BitList) -> BitList:
    state: State = State.from_S(S)
    l = state.l
    for ir in range(12 + 2 * l - nr, 12 + 2 * l):
        state = rnd(state=state, ir=ir)
    return state.to_S()


def keccak_f(S: BitList) -> BitList:
    l = b_to_l[len(S)]
    return keccak_p(nr=12 + 2 * l, S=S)


def split_to_blocks(message: BitList, block_size: int) -> List[BitList]:
    return [message[i:i + block_size] for i in range(0, len(message), block_size)]


def bitwise_xor(a, b):
    if len(a) != len(b):
        raise Exception("Arrays have to be the same lengths.")
    return [a ^ b for a, b in zip(a, b)]


def sponge(N: BitList, b: int, r: int, d: int):
    if not b == 1600:
        print("Warning: the state size is not 1600 bits. The results will not be compatible with SHA-3.")
    padded_message: BitList = N + pad(len(N), r)
    P: List[BitList] = split_to_blocks(padded_message, block_size=r)
    n = len(P)
    c = b - r
    S = [0] * b
    for i in range(n):
        S = keccak_f(bitwise_xor(S, P[i] + [0] * c))
    Z = []
    while True:
        Z += S[0:r]
        if len(Z) >= d:
            return Z[0:d]
        S = keccak_f(S=S)


def keccak(N: bytes, d: int, c: int, sha_mode: bool = False):
    N_compatible: BitList = bytes_to_bitlist(N, append_sha=sha_mode)
    result = sponge(N=N_compatible, d=d, r=1600 - c, b=1600)
    return bitlist_to_bytes(result)


def bytes_to_bitlist(bytelist: bytes, append_sha) -> BitList:
    bitstr = "".join([bin(byte)[2:].zfill(8) for byte in bytelist])
    bitlist = [int(flag) for flag in bitstr]
    if append_sha:
        bitlist += [0, 1]
    return bitlist


def bitlist_to_bytes(bitlist: BitList) -> bytes:
    result = b''
    for i in range(0, len(bitlist), 8):
        bit_string = "".join([str(bit) for bit in bitlist[i:i + 8]])
        byte = int(bit_string, base=2).to_bytes(length=1, byteorder="big")
        result += byte
    return result


def sha3_224(message: bytes):
    return keccak(message, c=448, d=224, sha_mode=True)


def sha3_256(message: bytes):
    return keccak(message, c=512, d=256, sha_mode=True)


def sha3_384(message: bytes):
    return keccak(message, c=768, d=384, sha_mode=True)


def sha3_512(message: bytes):
    return keccak(message, c=1024, d=512, sha_mode=True)


def get_hash(message: str, fun: Callable[[bytes], bytes]):
    message_bytes = message.encode()
    hash: bytes = fun(message_bytes)
    return hash.hex()


if __name__ == "__main__":
    m = "test string"*50
    hash = get_hash(m, sha3_256)
    print
