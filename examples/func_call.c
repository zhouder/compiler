/* 函数定义与调用示例：阶乘递归 */
int fact(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * fact(n - 1);
}

int main() {
    int result = fact(5);
    printf("%d\n", result);
    return 0;
}
