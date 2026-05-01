int sum(int a, int b) {
    return a + b;
}

int main() {
    return 0;
}

namespace math {
class Adder {
public:
    int sum(int x) { // must be detected as math::Adder::sum => fully qualified name
        return x;
    }  
};
}