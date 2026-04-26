# 计算当前内核的运算成本
scalar_multiply_sqr = (51 * 5 * 5) + (51 * 1 * 4)
scalar_multiply_mul = (51 * 5 * 11) + (51 * 1 * 12)

print('=== ec_scalar_multiply 成本 ===')
print(f'平方数: {scalar_multiply_sqr} (51×5×5 + 51×1×4)')
print(f'乘法数: {scalar_multiply_mul} (51×5×11 + 51×1×12)')

jac_to_affine_sqr = 255
jac_to_affine_mul = 15 + 3

print('\n=== jac_to_affine 成本 ===')
print(f'平方数: {jac_to_affine_sqr}')
print(f'乘法数: {jac_to_affine_mul}')

total_sqr = scalar_multiply_sqr + jac_to_affine_sqr
total_mul = scalar_multiply_mul + jac_to_affine_mul

print('\n=== 每个key总计 ===')
print(f'平方数: {total_sqr}')
print(f'乘法数: {total_mul}')

mod_inverse_sqr_ratio = jac_to_affine_sqr / total_sqr
mod_inverse_mul_ratio = jac_to_affine_mul / total_mul

print('\n=== mod_inverse 占比 ===')
print(f'平方中: {mod_inverse_sqr_ratio*100:.1f}%')
print(f'乘法中: {mod_inverse_mul_ratio*100:.1f}%')

batch_N = 256
montgomery_sqr = 1
montgomery_mul = 15 + 3 * (batch_N - 1)
montgomery_per_key_sqr = montgomery_sqr / batch_N
montgomery_per_key_mul = montgomery_mul / batch_N

print(f'\n=== Montgomery 每key成本 (N={batch_N}) ===')
print(f'平方数: {montgomery_per_key_sqr:.3f}')
print(f'乘法数: {montgomery_per_key_mul:.2f}')

print('\n=== 节省 ===')
print(f'平方: {jac_to_affine_sqr - montgomery_per_key_sqr:.3f}')
print(f'乘法: {jac_to_affine_mul - montgomery_per_key_mul:.2f}')
total_saved = (jac_to_affine_sqr - montgomery_per_key_sqr) + (jac_to_affine_mul - montgomery_per_key_mul)
total_current = jac_to_affine_sqr + jac_to_affine_mul
print(f'百分比: {total_saved/total_current*100:.1f}%')
