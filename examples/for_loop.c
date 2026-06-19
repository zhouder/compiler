/* for 循环示例：计算 1+2+...+10 */
int main() {
    int sum = 0;
    int i;
    for (i = 1; i <= 10; i = i + 1) {
        sum = sum + i;
    }
    printf("%d\n", sum);
    return 0;
}
