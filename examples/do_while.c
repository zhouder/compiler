/* do / while 循环示例：计算 5! */
int main() {
    int n = 5;
    int fact = 1;
    do {
        fact = fact * n;
        n = n - 1;
    } while (n > 0);
    printf("%d\n", fact);
    return 0;
}
