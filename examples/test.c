#include <stdio.h>

struct Pair {
    int x;
    int y;
};

int add_pair(struct Pair p) {
    return p.x + p.y;
}

int sum_array(int arr[], int n) {
    int i;
    int total;

    i = 0;
    total = 0;

    while (i < n) {
        if (i == 3) {
            i = i + 1;
            continue;
        }

        total = total + arr[i];

        if (total > 100) {
            break;
        }

        i = i + 1;
    }

    return total;
}

int main() {
    struct Pair p;
    int nums[5];
    int i;
    int result;

    p.x = 1;
    p.y = 2;
    scanf("%d", &p.x);

    nums[0] = p.x;
    nums[1] = p.y;

    i = 2;
    do {
        nums[i] = i;
        i = i + 1;
    } while (i < 5);

    result = sum_array(nums, 5);
    result = result + add_pair(p);

    printf("%d\n", result);
    return 0;
}
