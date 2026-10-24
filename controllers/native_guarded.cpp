// Trusted example plugin: deterministic stdin protocol, no clocks, randomness, sensors or files.
#include <iostream>
#include <set>
#include <string>
int main() {
    long long enter, exit, ageLimit;
    if (!(std::cin >> enter >> exit >> ageLimit)) return 1;
    long long now, id, sample, distance, present, latest=-1;
    bool active=false;
    std::set<long long> seen;
    while(std::cin >> now >> id >> sample >> distance >> present) {
        std::string reason="accepted";
        bool pulse=false;
        if(!present) reason="missing";
        else if(distance<0) reason="invalid";
        else if(seen.count(id)) reason="duplicate";
        else if(now-sample>ageLimit) reason="stale";
        else if(sample<=latest) reason="order";
        else {pulse=distance<(active?exit:enter); latest=sample;}
        if(present) seen.insert(id);
        active=pulse;
        std::cout << (pulse?"PULSE":"HOLD") << ' ' << reason << '\n';
    }
    return 0;
}
