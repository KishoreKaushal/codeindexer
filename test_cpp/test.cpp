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

// Tests for out-of-line definitions
namespace math {
class Subber { public: int sub(int x); };
} // namespace math

int math::Subber::sub(int x) { return -x; }

namespace math {
    class Multer { public: int mul(int x); };
    int Multer::mul(int x) { return x; }
} // namespace math

class Greeter { public: Greeter(int x); };
Greeter::Greeter(int x) {} // out-of-line constructor definition

struct Resource { Resource(){}  ~Resource(){} };  

// test for nested anonymous namespaces
namespace {
    void annon_namespace_func() {}
    namespace { void nested_annon_namespace_func() {} };
}