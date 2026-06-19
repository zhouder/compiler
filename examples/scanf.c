/* scanf 输入示例：读取两个整数并输出较大者 */
int max(int x, int y) {
    if (x > y) {
        return x;
    } else {
        return y;
    }
}

int main() {
    int a;
    int b;
    scanf("%d", &a);
    scanf("%d", &b);
    printf("%d\n", max(a, b));
    return 0;
}
