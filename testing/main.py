def inc(func):
    def newFunc(arg1):
        return func(arg1) + 1

    return newFunc


@inc
def my_function(arg1):
    return arg1


print(my_function)
print(my_function(5))
