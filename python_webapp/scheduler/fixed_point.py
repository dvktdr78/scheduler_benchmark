"""
17.14 고정소수점 연산

Pintos MLFQS에서 사용하는 고정소수점 연산 구현.

형식:
  - 32비트 정수 사용
  - 상위 17비트: 정수 부분
  - 하위 14비트: 소수 부분
  - F = 1 << 14 = 16384 (scaling factor)

참고:
  - Pintos 공식 문서: B.6 Fixed-Point Real Arithmetic
  - https://web.stanford.edu/class/cs140/projects/pintos/pintos_7.html#SEC135
"""


class FP:
    """고정소수점 연산 (17.14 포맷)"""

    F = 1 << 14  # 16384

    @staticmethod
    def int_to_fp(n: int) -> int:
        """정수를 고정소수점으로 변환"""
        return n * FP.F

    @staticmethod
    def fp_to_int_trunc(x: int) -> int:
        """고정소수점을 정수로 변환 (내림)"""
        return x // FP.F

    @staticmethod
    def fp_to_int_round(x: int) -> int:
        """고정소수점을 정수로 변환 (반올림)"""
        if x >= 0:
            return (x + FP.F // 2) // FP.F
        else:
            return (x - FP.F // 2) // FP.F

    @staticmethod
    def fp_add(x: int, y: int) -> int:
        """고정소수점 덧셈"""
        return x + y

    @staticmethod
    def fp_sub(x: int, y: int) -> int:
        """고정소수점 뺄셈"""
        return x - y

    @staticmethod
    def fp_add_int(x: int, n: int) -> int:
        """고정소수점 + 정수"""
        return x + n * FP.F

    @staticmethod
    def fp_sub_int(x: int, n: int) -> int:
        """고정소수점 - 정수"""
        return x - n * FP.F

    @staticmethod
    def fp_mul(x: int, y: int) -> int:
        """고정소수점 곱셈"""
        # 64비트로 확장하여 오버플로우 방지
        return (x * y) // FP.F

    @staticmethod
    def fp_mul_int(x: int, n: int) -> int:
        """고정소수점 * 정수"""
        return x * n

    @staticmethod
    def fp_div(x: int, y: int) -> int:
        """고정소수점 나눗셈"""
        # 64비트로 확장하여 정확도 유지
        return (x * FP.F) // y

    @staticmethod
    def fp_div_int(x: int, n: int) -> int:
        """고정소수점 / 정수"""
        return x // n


# 별칭 (편의성)
int_to_fp = FP.int_to_fp
fp_to_int_trunc = FP.fp_to_int_trunc
fp_to_int_round = FP.fp_to_int_round
fp_add = FP.fp_add
fp_sub = FP.fp_sub
fp_add_int = FP.fp_add_int
fp_sub_int = FP.fp_sub_int
fp_mul = FP.fp_mul
fp_mul_int = FP.fp_mul_int
fp_div = FP.fp_div
fp_div_int = FP.fp_div_int
