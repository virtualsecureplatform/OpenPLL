#include <iostream>
#include <N_DEV_Param.h>
int main() {
    std::cout << "device_parameter_bytes " << sizeof(Xyce::Device::Param) << '\n';
    std::cout << "double_value_bytes " << sizeof(Xyce::Util::ParamData<double>) << '\n';
    std::cout << "double_bytes " << sizeof(double) << '\n';
}
