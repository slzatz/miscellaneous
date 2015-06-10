def primes(int kmax):

    cdef int i, j, count
    cdef int primes[500]

    primes[0] = 2
    primes[1] = 3
    count = 3
    i = 5

    if kmax > 2000:
        kmax = 2000

    while count <= kmax:
        j = 1

        while 1:
           
            if  i%primes[j] == 0: 
                break

            elif primes[j]*primes[j] > i:
                if i < 500:
                    primes[count-1] = i
                count+=1
                break
            else:
                j+=1
  
        i+=2

    return i-2
