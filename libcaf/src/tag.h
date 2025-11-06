#ifndef TAG_H
#define TAG_H

#include <string>

class Tag {
public:
    const std::string name;
    const std::string commit_hash;

    Tag(const std::string& name, const std::string& commit_hash) : name(name), commit_hash(commit_hash) {}
};

#endif // TAG_H