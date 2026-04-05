#include <stdio.h>

int main() {
    int a;
    int b;
    int i;
    int sum;
    int max;
    int flag;
    char ch;
    float x;
    float y;
    float avg;

    a = 0;
    b = 0;
    i = 0;
    sum = 0;
    max = 0;
    flag = 0;
    ch = 'A';
    x = 3.5;
    y = 2.5;
    avg = 0.0;

    printf("please input a and b:\n");
    scanf("%d", &a);
    scanf("%d", &b);

    sum = a + b;
    sum = sum - 1;
    sum = sum * 2;
    sum = sum / 2;
    sum = sum % 5;

    if (a > b) {
        max = a;
        flag = 1;
    } else {
        max = b;
        flag = -1;
    }

    if (a == b) {
        printf("a == b\n");
    } else {
        if (a > b) {
            printf("a > b\n");
        } else {
            printf("a < b\n");
        }
    }

    i = 0;
    while (i < 5) {
        sum = sum + i;
        i = i + 1;
    }

    for (i = 1; i <= 3; i = i + 1) {
        sum = sum + i;
    }

    avg = (x + y) / 2.0;

    printf("%c\n", ch);
    printf("%f\n", avg);
    printf("%d\n", max);
    printf("%d\n", sum);

    return 0;
}