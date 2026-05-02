#include <iostream>

struct { int x; void foo_x(); } TestStructType;
struct { int x; void boo_y(); } A, B, C;
struct Node { int value; int get_value() {return value;} };

int main() { return 0; }
int sum(int a, int b) { return a + b; }

namespace math {
class Adder {
public:
    Adder(int base) {}
    int sum(int x) { return x; } 
    int sum(int x, int y) { return x + y; }
    friend std::ostream& operator<<(std::ostream& os, const Adder& a){
        return os << "Adder";
    }
    template<typename T> T multiply(T a, T b) { return a * b; }
};
} // namespace math

namespace { void foo() {} }

int math::Adder::sum(int x);
void helper(double x) {}