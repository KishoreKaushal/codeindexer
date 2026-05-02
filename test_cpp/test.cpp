int sum(int a, int b); // declaration 

int sum(int a, int b) {
    return a + b;
}

int main() {
    return 0;
}

namespace math {
class Adder {
public:
    Adder(int base) {} // kind must be ctor, not function

    int sum(int x) { // must be detected as math::Adder::sum => fully qualified name
        return x;
    } 
    
    int sum(int x, int y);

    int method(); // declaration only
    friend std::ostream& operator<<(std::ostream& os, const Adder& a){
        return os << "Adder";
    }

    template<typename T> T multiply(T a, T b) { // template method
        return a * b;
    }
};

Adder::method() { return 42; } // out-of-line-definition 


Adder::sum(int x, int y) { // overload, can be distinguished from other sum
    return x + y;
}

} // namespace math

namespace {
    void foo() { // must be detected as (annon)::foo => fully qualified name with anonymous namespace
    }
}

struct {
    void bar() { // must be detected as A::bar => fully qualified name with anonymous struct
    }
} A;